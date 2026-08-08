"""Unique point de contact LLM du backend (via le proxy LiteLLM).

Le backend n'appelle jamais un provider directement : il parle à LiteLLM
(`litellm_base_url`) avec un alias de tâche comme nom de modèle
(cf. .docs/17-llm-strategy.md). Si `litellm_base_url` est vide, toute la
couche LLM est désactivée et les appels retournent None — l'application
fonctionne à l'identique sans proxy (dev local, CI, Railway historique).
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.schemas.source import AuthorKind, SourceCategory, SourceFormat

logger = logging.getLogger(__name__)

_TIMEOUT = 45.0
# Le titre/auteur/date est presque toujours dans le début du document ;
# tronquer borne le coût et reste sous les limites de contexte des free tiers.
_MAX_INPUT_CHARS = 40_000


def resoudre_modele(alias: str) -> str:
    """Le modèle réel derrière un alias de tâche.

    En mode proxy, LiteLLM résout `biblio-parse` lui-même et l'alias part tel
    quel. En visant un provider directement, personne ne le résout : l'appel
    échouerait en 404 sur un modèle inconnu. `llm_direct_model` tranche.
    """
    direct = get_settings().llm_direct_model.strip()
    return direct or alias


async def _appel_json(
    alias: str,
    system: str,
    user: str,
    schema_name: str,
    schema: dict,
) -> str | None:
    """Un tour de chat qui doit rendre du JSON. Ne lève jamais, rend None.

    Deux tentatives au plus. La première demande une sortie contrainte par le
    schéma (`json_schema`), qui est la seule forme donnant une garantie. Les
    schémas produits par Pydantic contiennent des `anyOf` et des `$defs` que
    tous les providers n'acceptent pas ; un refus au niveau de la requête
    n'est pas un refus de la tâche, d'où le repli sur `json_object` avec le
    schéma recopié dans la consigne. Le parsing en aval valide dans les deux
    cas : rien n'est accepté sur la foi du mode demandé.
    """
    settings = get_settings()
    base = settings.litellm_base_url.rstrip("/")
    modele = resoudre_modele(alias)

    async def poste(response_format: dict, consigne: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            return await client.post(
                f"{base}/v1/chat/completions",
                json={
                    "model": modele,
                    "messages": [
                        {"role": "system", "content": consigne},
                        {"role": "user", "content": user},
                    ],
                    "response_format": response_format,
                    "temperature": 0,
                },
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )

    try:
        r = await poste(
            {"type": "json_schema", "json_schema": {"name": schema_name, "schema": schema}},
            system,
        )
        if r.status_code == 400:
            logger.info("LLM %s: schéma refusé, repli json_object", alias)
            r = await poste(
                {"type": "json_object"},
                f"{system}\n\nRends un objet JSON conforme à ce schéma :\n{json.dumps(schema)}",
            )
        if r.status_code != 200:
            logger.warning("LLM %s HTTP %s: %s", alias, r.status_code, r.text[:200])
            return None
        content: str = r.json()["choices"][0]["message"]["content"]
        return content
    except Exception as e:
        logger.warning("LLM %s failed: %s", alias, e)
        return None


class LlmSourceMetadata(BaseModel):
    """Sortie structurée de l'alias `metadata-extract`.

    Tous les champs sont optionnels : le LLM ne doit jamais inventer une
    valeur absente de la page (consigne système + champs nullable).
    """

    title: str | None = None
    authors: str | None = None
    published_at: str | None = None  # YYYY-MM-DD
    description: str | None = None
    format: SourceFormat | None = None
    category: SourceCategory | None = None
    author_kind: AuthorKind | None = None


_SYSTEM_PROMPT = (
    "Tu extrais les métadonnées bibliographiques d'une page web pour une fiche "
    "de sources. Réponds UNIQUEMENT avec le JSON demandé. Règles strictes : "
    "n'invente jamais une information absente du contenu (mets null) ; "
    "title = le titre de l'œuvre seul, sans le nom du site, de l'éditeur ou de "
    "la plateforme ni séparateur du type ' | ' ou ' - ' (ex. « Frontiers | Mémoire "
    "et vieillissement » → « Mémoire et vieillissement ») ; "
    "published_at au format YYYY-MM-DD ; authors = noms séparés par des virgules ; "
    "format/category/author_kind uniquement parmi les valeurs autorisées du schéma, "
    "null en cas de doute."
)


def parse_metadata_content(content: str) -> LlmSourceMetadata | None:
    """Parse et valide le contenu JSON renvoyé par le modèle. None si invalide."""
    try:
        return LlmSourceMetadata.model_validate_json(content)
    except ValidationError:
        # Une valeur d'enum hors taxonomie ne doit pas jeter tout le reste :
        # on retire les champs enum invalides et on retente.
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        for field in ("format", "category", "author_kind"):
            data.pop(field, None)
        try:
            return LlmSourceMetadata.model_validate(data)
        except ValidationError:
            return None


class LlmBiblioRef(BaseModel):
    """Une référence extraite d'une bibliographie collée en texte libre."""

    title: str | None = None
    authors: str | None = None
    year: int | None = None
    url: str | None = None
    doi: str | None = None
    category: SourceCategory | None = None


class LlmBiblioRefs(BaseModel):
    references: list[LlmBiblioRef] = []


_BIBLIO_SYSTEM_PROMPT = (
    "Tu analyses une bibliographie collée en texte libre (références APA, MLA, "
    "liste à puces, notes en vrac…) et tu en extrais chaque référence. Réponds "
    "UNIQUEMENT avec le JSON demandé. Règles strictes : n'invente jamais une "
    "information absente du texte (mets null) ; recopie url et doi exactement "
    "tels qu'ils apparaissent, sans en fabriquer ; authors = noms séparés par "
    "des virgules ; category uniquement parmi les valeurs autorisées du schéma, "
    "null en cas de doute."
)


def parse_biblio_content(content: str) -> list[LlmBiblioRef] | None:
    """Parse et valide le JSON de l'alias `biblio-parse`. None si invalide."""
    try:
        return LlmBiblioRefs.model_validate_json(content).references
    except ValidationError:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict) or not isinstance(data.get("references"), list):
            return None
        # Une catégorie hors taxonomie ne doit pas jeter toute la liste.
        for ref in data["references"]:
            if isinstance(ref, dict):
                ref.pop("category", None)
        try:
            return LlmBiblioRefs.model_validate(data).references
        except ValidationError:
            return None


_REF_BLOCK_SYSTEM_PROMPT = (
    "Tu extrais les métadonnées d'UNE SEULE référence bibliographique. Le texte "
    "peut être bruité (noms d'auteurs concaténés sans espaces comme "
    "'AdlemanN. E.MenonV.', volumes/pages collés au titre du journal, etc.). "
    "Réponds UNIQUEMENT avec le JSON demandé. Règles strictes : n'invente jamais "
    "une information absente (mets null) ; title = le titre de l'article seul "
    "sans le nom du journal ; authors = liste séparée par des virgules avec "
    "espaces corrects entre nom et initiale (ex. 'Adleman N., Menon V., "
    "Blasey C.') ; year = l'année entre parenthèses (2018) ; url et doi recopiés "
    "verbatim s'ils apparaissent."
)


async def parse_reference_block(block_text: str) -> LlmBiblioRef | None:
    """Extrait les métadonnées d'un bloc de texte représentant UNE ref.

    Utilisé en fallback quand :
      - le regex a capturé un DOI/URL sur ce bloc,
      - Crossref a échoué (DOI non indexé, timeout),
      - la ref a donc URL mais pas de title/authors.

    Le bloc doit être court (<500 chars). Retourne ``None`` si LLM désactivé
    ou en cas d'erreur — l'appelant garde la ref sans metadata.
    """
    settings = get_settings()
    if not settings.litellm_base_url:
        return None
    block = block_text.strip()[:2000]  # cap dur : une ref fait rarement > 500 chars
    if not block:
        return None

    content = await _appel_json(
        "biblio-parse",
        _REF_BLOCK_SYSTEM_PROMPT,
        block,
        "biblio_ref",
        LlmBiblioRef.model_json_schema(),
    )
    if content is None:
        return None
    try:
        return LlmBiblioRef.model_validate_json(content)
    except ValidationError:
        # Categorie invalide → retire et retente
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        data.pop("category", None)
        try:
            return LlmBiblioRef.model_validate(data)
        except ValidationError:
            return None


async def parse_bibliography(text: str) -> list[LlmBiblioRef] | None:
    """Extrait les références via l'alias `biblio-parse`. Never raises.

    Retourne None si la couche LLM est désactivée ou en cas d'erreur —
    l'appelant garde le résultat du parsing déterministe.
    """
    settings = get_settings()
    if not settings.litellm_base_url:
        return None

    content = await _appel_json(
        "biblio-parse",
        _BIBLIO_SYSTEM_PROMPT,
        text[:_MAX_INPUT_CHARS],
        "biblio_refs",
        LlmBiblioRefs.model_json_schema(),
    )
    return parse_biblio_content(content) if content is not None else None


_TRANSCRIPT_SYSTEM_PROMPT = (
    "Tu analyses la TRANSCRIPTION PARLÉE d'une vidéo et tu relèves les travaux "
    "explicitement mentionnés à l'oral : études, articles, livres, rapports. "
    "Réponds UNIQUEMENT avec le JSON demandé. Le texte vient d'une "
    "reconnaissance vocale : les noms propres sont souvent mal transcrits. "
    "Règles strictes : ne relève QUE ce qui est réellement nommé dans le texte ; "
    "n'invente jamais un titre, un auteur, une année, une url ou un doi qui "
    "n'y figure pas, mets null ; ne complète JAMAIS de mémoire une référence "
    "que tu crois reconnaître ; url et doi sont presque toujours null car on "
    "ne dicte pas une URL à l'oral ; ignore les mentions vagues sans titre ni "
    "auteur ('une étude a montré que…') ; si rien n'est nommé, renvoie une "
    "liste vide."
)


# Une heure de parole fait ~50 000 caracteres, soit plus que _MAX_INPUT_CHARS :
# sans decoupage, les mentions de la seconde moitie d'une video seraient
# perdues silencieusement. Le plafond de morceaux borne le cout LLM.
_TRANSCRIPT_CHUNK_CHARS = 30_000
_TRANSCRIPT_MAX_CHUNKS = 8


def split_transcript(text: str, size: int = _TRANSCRIPT_CHUNK_CHARS) -> list[str]:
    """Découpe en morceaux <= `size`, en coupant sur une frontière de mot."""
    chunks: list[str] = []
    rest = text.strip()
    while rest and len(chunks) < _TRANSCRIPT_MAX_CHUNKS:
        if len(rest) <= size:
            chunks.append(rest)
            break
        cut = rest.rfind(" ", 0, size)
        if cut <= 0:
            cut = size
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    return [c for c in chunks if c]


async def extract_mentioned_works(transcript: str) -> list[LlmBiblioRef] | None:
    """Travaux nommés à l'oral dans une transcription. Never raises.

    Distinct de `parse_bibliography` : le texte n'est pas une bibliographie
    rédigée mais de la parole transcrite automatiquement, donc bruitée. Le
    resultat est une suggestion a valider par l'utilisateur, jamais une
    reference autoritative.
    """
    settings = get_settings()
    if not settings.litellm_base_url:
        return None
    chunks = split_transcript(transcript)
    if not chunks:
        return None
    results = await asyncio.gather(*(_extract_works_from_chunk(c) for c in chunks))
    merged: list[LlmBiblioRef] = []
    for refs in results:
        merged.extend(refs or [])
    return merged


async def _extract_works_from_chunk(text: str) -> list[LlmBiblioRef] | None:
    content = await _appel_json(
        "biblio-parse",
        _TRANSCRIPT_SYSTEM_PROMPT,
        text[:_MAX_INPUT_CHARS],
        "biblio_refs",
        LlmBiblioRefs.model_json_schema(),
    )
    return parse_biblio_content(content) if content is not None else None


class LlmExcerpts(BaseModel):
    excerpts: list[str] = []


_EXCERPT_SYSTEM_PROMPT = (
    "Tu repères dans le texte d'une source les passages les plus cités ou "
    "citables : les phrases qui portent les affirmations clés du document. "
    "Réponds UNIQUEMENT avec le JSON demandé. Règles strictes : chaque extrait "
    "doit être recopié VERBATIM, mot pour mot, tel qu'il apparaît dans le "
    "texte — aucune reformulation, aucune traduction, aucune coupe interne ; "
    "2 à 5 extraits maximum, chacun de 1 à 3 phrases ; si un contexte est "
    "fourni, privilégie les passages qui s'y rapportent."
)


def parse_excerpts_content(content: str) -> list[str] | None:
    try:
        return LlmExcerpts.model_validate_json(content).excerpts
    except ValidationError:
        return None


async def suggest_excerpts(page_text: str, context: str | None = None) -> list[str] | None:
    """Suggère des citations verbatim via l'alias `excerpt-suggest`. Never raises.

    Retourne None si la couche LLM est désactivée ou en cas d'erreur.
    L'appelant DOIT vérifier que chaque extrait apparaît réellement dans le
    texte source (anti-hallucination) avant de l'exposer.
    """
    settings = get_settings()
    if not settings.litellm_base_url:
        return None

    user_content = f"Texte de la source :\n{page_text[:_MAX_INPUT_CHARS]}"
    if context:
        user_content = f"Contexte (fiche du créateur) : {context[:500]}\n\n{user_content}"

    content = await _appel_json(
        "excerpt-suggest",
        _EXCERPT_SYSTEM_PROMPT,
        user_content,
        "excerpts",
        LlmExcerpts.model_json_schema(),
    )
    return parse_excerpts_content(content) if content is not None else None


# --- Intitules d'extraits -------------------------------------------------
#
# Un extrait fait plusieurs centaines de caracteres ; dix empiles obligent a
# tout relire pour retrouver un passage. L'intitule est un reperage, pas un
# resume : il nomme le sujet du passage en quelques mots.


class LlmChunkTitles(BaseModel):
    titles: list[str] = []


_CHUNK_TITLE_SYSTEM_PROMPT = (
    "On te donne des passages numérotés issus d'un même texte. Pour chacun, "
    "écris un intitulé de repérage de 2 à 6 mots, dans la langue du passage, "
    "qui nomme ce dont il parle. Ce n'est ni un résumé ni une accroche : il "
    "sert à retrouver le passage dans une liste. Réponds UNIQUEMENT avec le "
    "JSON demandé, un intitulé par passage, dans le même ordre. Si un passage "
    "ne se laisse pas nommer, rends une chaîne vide plutôt qu'un intitulé "
    "approximatif."
)

_MAX_TITLE_CHARS = 200
# Une phrase, pas un resume : au-dela, la mise en situation prend le pas sur
# le passage qu'elle est censee servir. Meme plafond que la colonne.
_MAX_CONTEXT_CHARS = 500


async def suggest_chunk_titles(chunks: list[str]) -> list[str | None] | None:
    """Un intitule par passage, `None` la ou il n'y a rien a dire. Never raises.

    Rendre `None` plutot qu'un a-peu-pres est deliberé : un intitule faux se
    recopie dans la fiche sans que rien ne signale qu'il ne designe pas ce
    qu'il pretend designer (regle tenue en #317, #323, #327).
    """
    settings = get_settings()
    if not settings.litellm_base_url or not chunks:
        return None

    user_content = "\n\n".join(f"[{i + 1}] {c[:1500]}" for i, c in enumerate(chunks))
    content = await _appel_json(
        "excerpt-suggest",
        _CHUNK_TITLE_SYSTEM_PROMPT,
        user_content,
        "titles",
        LlmChunkTitles.model_json_schema(),
    )
    if content is None:
        return None
    try:
        return normalize_chunk_titles(LlmChunkTitles.model_validate_json(content).titles, chunks)
    except ValidationError:
        return None


def normalize_chunk_titles(titles: list[str], chunks: list[str]) -> list[str | None]:
    """Aligne les intitules sur les passages : un par passage, ni plus ni moins.

    Un modele qui en rend trop peu ne doit pas decaler les suivants ; un
    intitule vide ou trop long ne doit pas s'afficher.
    """
    sortie: list[str | None] = []
    for i in range(len(chunks)):
        brut = titles[i].strip() if i < len(titles) else ""
        sortie.append(brut[:_MAX_TITLE_CHARS] if brut else None)
    return sortie


# --- Mise en situation d'un extrait ---------------------------------------
#
# Un extrait voyage seul : export, reponse MCP, fiche publique. « Ce modele
# distingue trois composantes » ne nomme ni son objet ni son auteur, et qui le
# rencontre isole ne peut pas savoir de quoi il traite. La phrase de mise en
# situation restitue ces reperes -- elle ne resume pas le passage, elle dit ce
# que le passage suppose connu.


class LlmAnnotation(BaseModel):
    title: str | None = None
    context: str | None = None


_ANNOTATION_SYSTEM_PROMPT = (
    "On te donne un passage extrait d'un document, et l'entourage d'ou il vient. "
    "Tu produis deux choses. `title` : un intitulé de repérage de 2 à 6 mots, "
    "dans la langue du passage, qui nomme ce dont il parle — ni résumé ni "
    "accroche, il sert à retrouver le passage dans une liste. `context` : UNE "
    "phrase, 40 mots maximum, qui situe le passage pour quelqu'un qui le "
    "rencontre seul, hors de son document — de quel texte il vient, de quoi il "
    "traite, à quoi renvoient ses pronoms et ses démonstratifs. Réponds "
    "UNIQUEMENT avec le JSON demandé. Règles strictes : ne réutilise pas les "
    "mots du passage pour les paraphraser, apporte ce qu'il ne dit pas ; "
    "n'affirme rien que l'entourage ne permette d'établir ; si l'entourage ne "
    "suffit pas à situer honnêtement le passage, rends null plutôt qu'une "
    "approximation."
)


async def suggest_annotation(passage: str, entourage: str = "") -> LlmAnnotation | None:
    """Intitule et mise en situation d'un passage. Never raises.

    Rendre `None` plutot qu'un a-peu-pres est la meme regle que pour les
    intitules : cette prose s'affiche a cote d'un verbatim, et une mise en
    situation fausse ferait porter au passage un sens que sa source ne lui
    donne pas. L'appelant l'expose comme une proposition a valider, jamais
    comme un acquis.
    """
    settings = get_settings()
    if not settings.litellm_base_url or not passage.strip():
        return None

    user_content = f"Passage :\n{passage[:2000]}"
    if entourage.strip():
        user_content = f"Entourage :\n{entourage[:6000]}\n\n{user_content}"

    content = await _appel_json(
        "excerpt-suggest",
        _ANNOTATION_SYSTEM_PROMPT,
        user_content,
        "annotation",
        LlmAnnotation.model_json_schema(),
    )
    if content is None:
        return None
    try:
        annotation = LlmAnnotation.model_validate_json(content)
    except ValidationError:
        return None
    return LlmAnnotation(
        title=(annotation.title or "").strip()[:_MAX_TITLE_CHARS] or None,
        context=(annotation.context or "").strip()[:_MAX_CONTEXT_CHARS] or None,
    )


# --- Classifieur : type d'URL (source | promo | social | other) -----------
#
# Utilise pour distinguer les vraies references bibliographiques des liens
# promotionnels (Amazon, Patreon), des URLs de reseau social (X, TikTok),
# et des autres pages sans valeur bibliographique. L'utilisateur voit un
# badge colore par type dans la preview et coche/decoche a sa guise --
# le LLM propose, l'user tranche.


class LlmUrlClassification(BaseModel):
    """Classification d'une URL par le LLM."""

    type: str


_URL_CLASSIFY_SYSTEM_PROMPT = (
    "Tu classifies une URL trouvee dans le texte / la description d'un contenu. "
    "Reponds UNIQUEMENT avec le JSON demande, un seul champ `type`. Valeurs "
    "autorisees : 'source' (reference bibliographique : article scientifique, "
    "papier, livre cite, journal, DOI, page institutionnelle) ; 'promo' (lien "
    "promotionnel : Amazon, boutique, Patreon, cours payant, chaine premium, "
    "affiliation) ; 'social' (reseau social : X, Twitter, TikTok, Instagram, "
    "YouTube (chaine ou short), Bluesky, Threads, LinkedIn) ; 'other' (rien "
    "de tout ca ou incertain). Le contexte adjacent (emojis, texte avant l'URL) "
    "aide beaucoup : \U0001f4da / 'References' / 'Sources' / 'Cites' -> probablement "
    "source ; \U0001f6d2 / 'Mon livre' / 'Achetez' / 'Sponsor' -> promo ; 'Suivez-moi' / "
    "'Rejoignez ma chaine' -> social."
)


async def classify_url_type(url: str, context: str = "") -> str | None:
    """Classifie une URL en source / promo / social / other via LLM.

    ``context`` : texte adjacent (une ou deux phrases). Aide fortement la
    classification. Vide accepte mais reduit la fiabilite.

    Retourne None si LLM off ou en cas d'erreur.
    """
    settings = get_settings()
    if not settings.litellm_base_url:
        return None
    user_content = f"URL : {url}"
    if context:
        user_content += f"\n\nContexte adjacent :\n{context[:1500]}"

    content = await _appel_json(
        "biblio-parse",
        _URL_CLASSIFY_SYSTEM_PROMPT,
        user_content,
        "url_classification",
        LlmUrlClassification.model_json_schema(),
    )
    if content is None:
        return None
    try:
        parsed = LlmUrlClassification.model_validate_json(content)
    except ValidationError:
        return None
    t = parsed.type.lower().strip()
    return t if t in ("source", "promo", "social", "other") else None


async def extract_metadata(page_text: str, url: str) -> LlmSourceMetadata | None:
    """Extrait les métadonnées via l'alias `metadata-extract`. Never raises.

    Retourne None si la couche LLM est désactivée ou en cas d'erreur —
    l'appelant (extracteur heuristique) reste la source de vérité.
    """
    settings = get_settings()
    if not settings.litellm_base_url:
        return None

    content = await _appel_json(
        "metadata-extract",
        _SYSTEM_PROMPT,
        f"URL : {url}\n\nContenu de la page :\n{page_text[:_MAX_INPUT_CHARS]}",
        "source_metadata",
        LlmSourceMetadata.model_json_schema(),
    )
    return parse_metadata_content(content) if content is not None else None
