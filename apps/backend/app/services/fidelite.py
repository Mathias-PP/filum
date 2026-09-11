"""Le juge de fidelite : la source dit-elle ce que l'annotation lui fait dire.

La relecture d'ancrage (`verify_excerpts`) demande « ces mots sont-ils dans la
page ». C'est une question de presence, et elle ne suffit pas : un passage
retrouve au mot pres peut servir a etayer le contraire de ce qu'il affirme.
Le titre et la mise en situation, eux, ne sont pas dans la page. Quand ils
viennent d'un modele, rien jusqu'ici ne les confrontait au texte.

**Le verificateur n'est pas le generateur.** L'annotation est produite par
`services/llm.py` sur la cle serveur ; le juge tourne sur la cle du createur,
souvent sur une autre famille de modeles. Ce sont deja deux appels distincts
sur deux cles distinctes, et cette propriete est la garde la moins chere du
dispositif. Ne pas la defaire en « simplifiant » plus tard vers un appel unique.

**Le juge n'utilise que la cle du createur.** Pas le mode gratuit : son quota
est un budget de conversation, et une fiche d'une douzaine d'extraits annotes
le viderait en une passe, laissant le createur sans agent. Pas la cle serveur
de `services/llm.py` non plus, qui est celle du generateur. Sans cle, pas de
verdict, et l'absence se dit.

**Le juge avertit, il ne bloque jamais.** Aucun verdict n'empeche de publier.
Son echec est un etat affiche, pas une exception qui remonte.

Le juge n'a jamais ete mesure contre un corrige. Il part quand meme, et le dit :
livrer sans mesure est acceptable, promettre sans mesure ne l'est pas.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from app.models.agent_provider import AgentProvider
from app.models.source import Source
from app.models.source_excerpt import SourceExcerpt
from app.models.user import User
from app.services.llm_adapters import (
    format_chat_payload,
    parse_blocking_response,
    url_et_headers,
)

logger = logging.getLogger(__name__)

_TIMEOUT = 90.0
_MAX_TOKENS = 2000

#: Les six verdicts, et rien d'autre. Une valeur hors de cette liste est
#: rejetee, jamais rapprochee de la plus proche : un verdict approximatif se
#: lirait comme un verdict, alors qu'il ne veut rien dire.
VERDICTS: frozenset[str] = frozenset(
    {
        "soutient",
        "contredit",
        "mixte",
        "ne_traite_pas",
        "preuve_insuffisante",
        "ambigu",
    }
)

#: Sur quoi le juge s'est prononce. Se declare toujours : pretendre avoir juge
#: sur le texte integral quand on n'a lu qu'un resume est un mensonge par
#: omission, et c'est exactement celui que ce champ existe pour empecher.
PORTEES: frozenset[str] = frozenset({"texte_integral", "resume_seul", "metadonnees_seules"})

#: Les seuls verdicts qui survivent a l'absence du texte de la source.
#:
#: Un desaccord rendu sans avoir lu la source vaut encore quelque chose : il
#: signale que l'annotation entre en tension avec ce qu'on sait par ailleurs.
#: Un accord rendu dans les memes conditions ne vaut rien, puisque rien ne
#: l'etaye. L'asymetrie est voulue.
_SURVIVENT_SANS_TEXTE: frozenset[str] = frozenset({"contredit", "mixte"})

AVERTISSEMENT_NON_MESURE = (
    "Ce juge n'a jamais ete mesure contre un corpus corrige. Son verdict est "
    "une indication a verifier, pas une preuve."
)

_SYSTEME = """Tu relis des citations pour verifier qu'elles disent bien ce qu'on leur fait dire.

On te donne, pour chaque passage : le verbatim cite, puis le titre et la mise
en situation qu'un autre modele a ecrits a son sujet. Ta seule question est :
le passage, dans le texte qui l'entoure, soutient-il ce que le titre et la mise
en situation lui font dire ?

Trois questions, dans cet ordre, et la troisieme ne se pose que si les deux
premieres sont franchies :

1. Pertinence : ce passage traite-t-il de ce que l'annotation lui fait dire ?
2. Verifiabilite : le texte disponible permet-il de trancher ?
3. Position : soutient, contredit, ou les deux a la fois.

Rends exactement l'un de ces six verdicts, jamais un autre mot :

- "soutient" : le passage etaye ce que l'annotation lui fait dire.
- "contredit" : le passage dit le contraire, ou l'annotation lui prete une
  portee que le texte refuse explicitement.
- "mixte" : le passage etaye une partie et contredit une autre.
- "ne_traite_pas" : le passage parle d'autre chose. A ne rendre que si tu as
  lu le passage et son entourage.
- "preuve_insuffisante" : tu n'as pas eu de quoi trancher. C'est le verdict
  quand la page n'a pas pu etre lue. L'absence de preuve n'est jamais
  "ne_traite_pas" : le silence de ce texte-ci n'est pas le silence de la
  litterature.
- "ambigu" : le texte est lisible mais se prete aux deux lectures.

Aucun score, aucun pourcentage, aucune note sur dix. Une phrase de motif, en
francais, qui dit ce qui t'a decide.

Reponds par un tableau JSON et rien d'autre, un objet par passage, dans
l'ordre recu :

[{"n": 1, "verdict": "soutient", "motif": "..."}]"""


@dataclass(frozen=True)
class VerdictExtrait:
    excerpt_id: UUID
    verdict: str
    portee: str
    note: str


@dataclass(frozen=True)
class Rapport:
    """Ce qu'une passe de jugement a produit. Ne leve jamais, se lit toujours."""

    verdicts: list[VerdictExtrait]
    #: Ce qui a empeche de juger, en clair. `None` quand la passe a abouti.
    #: Un motif ici n'est pas une erreur du createur : c'est un etat a afficher.
    erreur: str | None = None
    avertissement: str = AVERTISSEMENT_NON_MESURE


def portee_pour(page_text: str, complet: bool) -> str:
    """Sur quoi le juge va se prononcer, d'apres ce qu'on a reellement en main.

    Deduite de ce qui a ete lu, jamais annoncee par le modele : un modele a qui
    on demande sur quoi il s'est prononce repond ce qui l'arrange.
    """
    if not page_text.strip():
        return "metadonnees_seules"
    return "texte_integral" if complet else "resume_seul"


def declasser(verdict: str, portee: str) -> tuple[str, str | None]:
    """Applique l'asymetrie de la preuve. Rend `(verdict, motif)`.

    Sans le texte de la source, un accord ne vaut rien et un desaccord vaut
    encore quelque chose. Le motif est `None` quand rien n'a ete declasse.
    """
    if portee != "metadonnees_seules" or verdict in _SURVIVENT_SANS_TEXTE:
        return verdict, None
    if verdict == "preuve_insuffisante":
        return verdict, None
    return (
        "preuve_insuffisante",
        f"Verdict « {verdict} » rendu sans le texte de la source, donc declasse : rien ne l'etaye.",
    )


def _extraire_json(brut: str) -> list[dict[str, Any]] | None:
    """Le tableau JSON dans la reponse, quoi qu'il y ait autour.

    Les modeles enrobent volontiers leur JSON de ``` ou d'une phrase
    d'introduction. Refuser ces reponses ferait perdre un verdict valide pour
    une question de presentation.
    """
    texte = brut.strip()
    if not texte:
        return None
    debut, fin = texte.find("["), texte.rfind("]")
    if debut == -1 or fin <= debut:
        return None
    try:
        charge = json.loads(texte[debut : fin + 1])
    except json.JSONDecodeError:
        return None
    return charge if isinstance(charge, list) else None


def _texte_du_message(message: dict[str, Any]) -> str:
    contenu = message.get("content")
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        return "".join(
            b.get("text", "") for b in contenu if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _bloc_du_passage(indice: int, extrait: SourceExcerpt, entourage: str) -> str:
    parts = [f"### Passage {indice}", "", "Verbatim cite :", f"> {extrait.text.strip()}", ""]
    if extrait.title:
        parts += [f"Titre propose : {extrait.title}", ""]
    if extrait.context:
        parts += [f"Mise en situation proposee : {extrait.context}", ""]
    if entourage:
        parts += ["Texte qui entoure le passage dans la source :", "", entourage, ""]
    else:
        parts += [
            "Le texte de la source n'a pas pu etre lu pour ce passage.",
            "",
        ]
    return "\n".join(parts)


def a_juger(extraits: list[SourceExcerpt]) -> list[SourceExcerpt]:
    """Les extraits que le juge relit : ceux qu'un modele a touches.

    Un extrait saisi a la main par le createur n'est pas relu. Ce n'est pas
    qu'il serait au-dessus de tout soupcon : c'est que le createur repond de ce
    qu'il ecrit, alors que personne ne repond de ce qu'un modele a propose.
    """
    return [e for e in extraits if e.annotated_by_ai or e.suggested_by_ai]


async def _appeler(
    provider: AgentProvider,
    messages: list[dict[str, Any]],
    transport: httpx.AsyncBaseTransport | None,
) -> tuple[str | None, str | None]:
    """Un appel bloquant. Rend `(texte, erreur)`, dont exactement un est None."""
    from app.services.agent_providers import _decrypt

    try:
        cle = _decrypt(provider.api_key_enc)
        url, headers = url_et_headers(provider.provider, provider.base_url, cle)
        charge = format_chat_payload(
            provider.provider, provider.model, messages, [], _MAX_TOKENS, stream=False
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT, transport=transport) as client:
            reponse = await client.post(url, json=charge, headers=headers)
        if reponse.status_code != 200:
            return None, f"Le fournisseur a repondu {reponse.status_code}."
        resultat = parse_blocking_response(provider.provider, reponse.json())
    except Exception as e:  # le juge avertit, il ne casse rien
        logger.warning("Juge de fidelite injoignable : %s", e)
        return None, f"Juge de fidelite injoignable : {type(e).__name__}."
    if isinstance(resultat, str):
        return None, resultat
    return _texte_du_message(resultat[0]), None


async def juger(
    user: User,
    source: Source,
    extraits: list[SourceExcerpt],
    page_text: str,
    *,
    complet: bool,
    provider: AgentProvider | None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Rapport:
    """Relit les extraits annotes par un modele. Ne leve jamais.

    `page_text` et `complet` viennent de la lecture que l'appelant a deja
    faite : le juge ne retelecharge rien, et la portee qu'il declare est
    deduite de ce que cette lecture a rendu.
    """
    from app.mcp_server.tools_write import _entourage_du_passage

    if not user.fidelity_judge_enabled:
        return Rapport([], erreur=None)
    cibles = a_juger(extraits)
    if not cibles:
        return Rapport([], erreur=None)
    if provider is None:
        return Rapport(
            [],
            erreur=(
                "Aucune cle configuree : le juge de fidelite n'a pas tourne. "
                "Ajoutez une cle dans Cles pour qu'il relise ce que l'IA annote."
            ),
        )

    portee = portee_pour(page_text, complet)
    blocs = [
        _bloc_du_passage(i, e, _entourage_du_passage(page_text, e.text))
        for i, e in enumerate(cibles, start=1)
    ]
    entete = f"Source : {source.title or source.url}"
    messages = [
        {"role": "system", "content": _SYSTEME},
        {"role": "user", "content": entete + "\n\n" + "\n".join(blocs)},
    ]

    texte, erreur = await _appeler(provider, messages, transport)
    if erreur is not None:
        return Rapport([], erreur=erreur)
    lignes = _extraire_json(texte or "")
    if lignes is None:
        return Rapport([], erreur="Le juge n'a pas rendu de JSON lisible.")

    par_indice: dict[int, dict[str, Any]] = {}
    for ligne in lignes:
        if not isinstance(ligne, dict):
            continue
        try:
            n = int(ligne["n"])
        except (KeyError, TypeError, ValueError):
            continue
        par_indice[n] = ligne

    verdicts: list[VerdictExtrait] = []
    for i, extrait in enumerate(cibles, start=1):
        ligne = par_indice.get(i)
        if ligne is None:
            continue
        brut = str(ligne.get("verdict") or "").strip().lower()
        if brut not in VERDICTS:
            # Rejete, jamais rapproche du plus proche : « plutot favorable » ne
            # devient pas « soutient », parce que ce n'est pas la meme chose.
            logger.info("Verdict hors enumeration ecarte : %r", brut)
            continue
        note = str(ligne.get("motif") or "").strip()
        retenu, declassement = declasser(brut, portee)
        if declassement:
            note = f"{declassement} {note}".strip()
        verdicts.append(
            VerdictExtrait(excerpt_id=extrait.id, verdict=retenu, portee=portee, note=note)
        )
    return Rapport(verdicts, erreur=None)


def appliquer(extraits: list[SourceExcerpt], rapport: Rapport) -> int:
    """Pose les verdicts sur les extraits. L'appelant commit. Rend le compte."""
    par_id = {e.id: e for e in extraits}
    releve_le = datetime.now(UTC).replace(tzinfo=None)
    poses = 0
    for v in rapport.verdicts:
        extrait = par_id.get(v.excerpt_id)
        if extrait is None:
            continue
        extrait.fidelity_verdict = v.verdict
        extrait.fidelity_scope = v.portee
        extrait.fidelity_checked_at = releve_le
        extrait.fidelity_note = v.note or None
        poses += 1
    return poses


def en_attente(extraits: list[SourceExcerpt]) -> int:
    """Extraits qu'un modele a touches et que le juge n'a jamais relus.

    Un juge actif mais jamais execute laisse la fiche exactement aussi peu
    verifiee que si personne ne l'avait active. Ce compte est ce qui permet de
    le dire a la publication plutot que de laisser croire le contraire.
    """
    return sum(1 for e in a_juger(extraits) if e.fidelity_verdict is None)


def resume_verdicts(extraits: list[SourceExcerpt]) -> dict[str, int]:
    """Compte par verdict, pour affichage. Les extraits jamais juges s'excluent."""
    compte: dict[str, int] = {}
    for e in a_juger(extraits):
        if e.fidelity_verdict:
            compte[e.fidelity_verdict] = compte.get(e.fidelity_verdict, 0) + 1
    return compte
