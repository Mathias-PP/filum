# Fiches plus complètes : plan d'implémentation

> **Pour l'agent qui exécute :** sous-compétence requise :
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans`, tâche par tâche. Les étapes utilisent des cases
> à cocher (`- [ ]`).

**Goal :** qu'un agent, petit modèle compris, produise sur n'importe quel sujet
des fiches qui explorent beaucoup de sources, ne retiennent que celles qui
portent des extraits pertinents, et en tirent le plus d'extraits utiles.

**Architecture :** le déroulé guidé du chat (`services/deroule_guide.py`, #660)
devient une exploration. Le serveur propose des passages exacts classés par le
sens, le modèle choisit. Une source n'entre dans la fiche qu'avec ses extraits.
Un plan de couverture et une borne par rendement décident quand s'arrêter.

**Tech Stack :** FastAPI, SQLAlchemy async, pytest, httpx `MockTransport`,
SvelteKit 5, vitest. Embeddings `gemini-embedding-001` via `services/embeddings.py`.

**Spécification :** `agent/plans/2026-09-13-fiches-plus-completes.md`. Les
identifiants entre parenthèses (A1, B2…) renvoient à ses sections.

---

## Règles pour toute la série

- **Une PR à la fois**, toujours `--base main`, jamais empilée. Merger, déployer,
  vérifier en prod, puis passer à la suivante.
- **Français partout.** Commentaires backend en ASCII sans accents, textes vus
  par un humain accentués. **Aucun tiret cadratin** (U+2014), nulle part :
  le chercher avec `grep -c` sur chaque fichier touché.
- **Aucun quota arbitraire.** Une borne technique se justifie dans son
  commentaire ; une borne éditoriale n'existe pas, l'arrêt se fait au rendement.
- **Tout sujet.** Chaque test d'exemple qui porte sur un sujet en prend un hors
  santé au moins une fois (histoire, économie, droit, technique, culture).
- **Formater avant de committer** : `uv run ruff format app tests` et
  `npx prettier --write <fichiers>` ; sinon la CI de lint casse.
- **Suite après la dernière édition** : un run lancé au milieu des éditions donne
  un vert périmé.
- **Ne jamais appeler un modèle depuis la VM.** Le banc tourne sur un poste de
  développement.

### Commandes

```bash
# Backend, depuis apps/backend
rm -f test.db && CI=true uv run pytest tests/unit -q -p no:cacheprovider
CI=true uv run pytest tests/integration -q -p no:cacheprovider
uv run ruff check app tests && uv run ruff format app tests
uv run mypy <fichiers touches> --ignore-missing-imports
CI=true uv run python -m app.scripts.export_openapi   # si une route change

# Frontend, depuis apps/frontend
pnpm run check && npx eslint <fichiers> && npx vitest run
pnpm run generate:api && npx prettier --write src/lib/api/generated.ts   # si une route change

# PR (jeton gh depuis le gestionnaire d'identifiants Git)
export GH_TOKEN=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill | grep '^password=' | cut -d= -f2)
gh pr create --base main --head <branche> --title "..." --body "..."

# Deploiement VM apres merge
ssh -i ~/.ssh/id_ed25519 mathias.pinault@philum-api.duckdns.org \
  "sudo -n -u mathias_pinault bash -c 'cd ~/filum && git pull --ff-only origin main' && \
   sudo -n bash -c 'cd /home/mathias_pinault/filum/infra/oracle && docker compose -f docker-compose.micro.yml up -d --build backend'"
curl -s https://philum-api.duckdns.org/health
```

---

## Découpage

La spécification couvre plusieurs sous-systèmes indépendants. Les PR 1 à 3
posent la fondation et sont détaillées ici jusqu'au code. Les PR 4 à 8 fixent
leurs fichiers, leurs interfaces, leurs tests et leurs critères d'acceptation ;
chacune reçoit son plan détaillé (même format que les PR 1 à 3) au moment de la
commencer, parce que leurs réglages dépendent de ce que le banc mesurera après
les PR précédentes.

| PR | Branche | Contenu | Spécification |
|---|---|---|---|
| 1 | `fix/openalex-cle-api` | clé d'API OpenAlex sur tous les appels | A2 (bug prod possible) |
| 2 | `feat/agent-passages-proposes` | le serveur propose des passages exacts, par le sens | B2 |
| 3 | `feat/agent-exploration-atomique` | une source n'entre qu'avec ses extraits ; déroulé en exploration | B1, B3 |
| 4 | `feat/agent-plan-de-couverture` | sous-questions, rendement, indicateur de couverture | A1, D2, D3 |
| 5 | `feat/agent-recherche-par-famille` | recherche par familles, nature des sources, texte intégral, références, corpus Philum | A2, A3, A4, A5, A6 |
| 6 | `feat/agent-relecteur` | grille de relecture qui relance l'exploration ; extraction exhaustive ; nuance par source | D1, B4, B5 |
| 7 | `feat/agent-synthese-ancree` | synthèse ancrée, annotation structurée, mise en situation, redites, pivots et connexions | C1, C2, C3, B6, B7 |
| 8 | `feat/agent-banc-elargi` | banc sur toutes les disciplines, nouveaux chiffres, routage par étape | F, E |

### Carte des fichiers

| Fichier | Rôle | PR |
|---|---|---|
| `app/extractors/openalex_client.py` (créé) | paramètres communs des appels OpenAlex | 1 |
| `app/services/passages_candidats.py` (créé) | découpe une page et classe ses passages par sous-question | 2 |
| `app/mcp_server/tools_write.py` | outil `propose_passages` | 2 |
| `app/agent_tools/philum.py` | catalogue ; garde « pas de source sans extrait » | 2, 3 |
| `app/services/deroule_guide.py` | étapes du déroulé : exploration, plan, rendement, relecture | 3, 4, 6 |
| `app/services/couverture.py` (créé) | couverture d'une fiche par sous-question | 4 |
| `app/agent_tools/litterature.py` (créé) | recherche par famille, références | 5 |
| `app/services/relecture.py` (créé) | grille de relecture calculée | 6 |
| `app/services/synthese.py` (créé) | vérification des renvois d'une synthèse | 7 |
| `app/scripts/banc_agent.py` | questions et chiffres élargis | 8 |
| `apps/frontend/src/lib/components/chat/FicheVivante.svelte` | indicateur de couverture | 4 |
| `apps/frontend/src/lib/agent/toolLabels.ts` | libellés des nouveaux outils | 2, 5 |

---

## PR 1 : clé d'API OpenAlex

**Pourquoi :** depuis le 13 février 2026, OpenAlex exige une clé gratuite ; sans
clé, 100 crédits par jour
([annonce](https://groups.google.com/g/openalex-users/c/rI1GIAySpVQ),
[authentification](https://help.openalex.org/api/authentication/)). Les deux
appels du code n'en passent pas.

**Files :**
- Create : `apps/backend/app/extractors/openalex_client.py`
- Modify : `apps/backend/app/core/config.py` (après `embedding_model`)
- Modify : `apps/backend/app/extractors/open_access.py` (`check_open_access`)
- Modify : `apps/backend/app/extractors/openalex_metadonnees.py` (`chercher_par_doi`)
- Test : `apps/backend/tests/unit/test_openalex_client.py`

- [ ] **Étape 1 : vérifier le nom du paramètre d'authentification.** Information
  périssable : ouvrir https://help.openalex.org/api/authentication/ et confirmer
  que la clé passe en paramètre de requête `api_key`. Si la documentation dit
  autre chose (en-tête), adapter l'étape 4 en conséquence.

- [ ] **Étape 2 : écrire le test qui échoue**

```python
"""Tous les appels a OpenAlex portent la cle d'API quand elle est posee."""

from __future__ import annotations

from app.core.config import get_settings
from app.extractors.openalex_client import parametres_openalex


def test_sans_cle_aucun_parametre(monkeypatch):
    monkeypatch.setattr(get_settings(), "openalex_api_key", "")
    assert parametres_openalex() == {}


def test_avec_cle_le_parametre_est_pose(monkeypatch):
    monkeypatch.setattr(get_settings(), "openalex_api_key", "cle-test")
    assert parametres_openalex() == {"api_key": "cle-test"}
```

- [ ] **Étape 3 : lancer le test**

Run : `CI=true uv run pytest tests/unit/test_openalex_client.py -q`
Attendu : échec, `ModuleNotFoundError: app.extractors.openalex_client`.

- [ ] **Étape 4 : implémenter**

`app/core/config.py`, après `embedding_model` :

```python
    # OpenAlex exige une cle d'API depuis le 2026-02-13. Sans cle, 100 credits
    # par jour : la resolution des metadonnees et de l'acces libre s'eteint en
    # quelques dizaines d'appels. Cle gratuite sur openalex.org/settings/api.
    openalex_api_key: str = ""
```

`app/extractors/openalex_client.py` :

```python
"""Parametres communs a tous les appels OpenAlex.

Un seul endroit pour la cle : un appel qui l'oublierait retomberait sur le
budget sans cle, sans que rien ne le signale.
"""

from __future__ import annotations

from app.core.config import get_settings


def parametres_openalex() -> dict[str, str]:
    cle = get_settings().openalex_api_key.strip()
    return {"api_key": cle} if cle else {}
```

Dans `open_access.py` et `openalex_metadonnees.py`, remplacer l'appel :

```python
            r = await client.get(
                f"https://api.openalex.org/works/doi:{cleaned}", params=parametres_openalex()
            )
```

(`propre` au lieu de `cleaned` dans `openalex_metadonnees.py`), et ajouter
`from app.extractors.openalex_client import parametres_openalex`.

- [ ] **Étape 5 : un test par appel**, dans le même fichier de test :

```python
import httpx
import pytest

from app.extractors import open_access, openalex_metadonnees


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "appel",
    [
        lambda: open_access.check_open_access("10.1000/x"),
        lambda: openalex_metadonnees.chercher_par_doi("10.1000/x"),
    ],
)
async def test_chaque_appel_porte_la_cle(monkeypatch, appel):
    vus: list[httpx.URL] = []
    vrai_client = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda requete: vus.append(requete.url) or httpx.Response(404)
        )
        return vrai_client(*args, **kwargs)

    monkeypatch.setattr(get_settings(), "openalex_api_key", "cle-test")
    monkeypatch.setattr(httpx, "AsyncClient", client)
    await appel()
    assert vus and vus[0].params.get("api_key") == "cle-test"
```

- [ ] **Étape 6 : lancer les tests, puis toute la suite unitaire.** Attendu : vert.
- [ ] **Étape 7 : commit, PR.** Titre : `fix(openalex): la cle d'API accompagne chaque appel`.
- [ ] **Étape 8 : en prod.** Demander au créateur de créer la clé et de la poser
  dans `infra/oracle/.env` sous `openalex_api_key` (nom en minuscules : les
  réglages sont sensibles à la casse). Redémarrer le backend, puis vérifier
  qu'une source à DOI récupère titre et accès libre.

**Critère d'acceptation :** en prod, une source ajoutée avec un DOI a son titre
résolu et son statut d'accès libre renseigné.

---

## PR 2 : passages proposés par le serveur (B2)

**Pourquoi :** mesuré, 79 extraits refusés sur 83 avec un modèle de 8 milliards
de paramètres. Le modèle recopiait ou reformulait. Ici, le serveur rend des
passages exacts, classés par le sens pour chaque question ; le modèle choisit.
L'outil prend une **adresse**, pas un identifiant de source : à la PR 3, on
explore une candidate avant de l'ajouter.

**Files :**
- Create : `apps/backend/app/services/passages_candidats.py`
- Modify : `apps/backend/app/mcp_server/tools_write.py` (nouvel outil `propose_passages`)
- Modify : `apps/backend/app/mcp_server/server.py` (enregistrement MCP)
- Modify : `apps/backend/app/agent_tools/philum.py` (`_ECRITURE`)
- Modify : `apps/backend/app/services/agent.py` (`LECTURES_REPRISES`)
- Modify : `apps/frontend/src/lib/agent/toolLabels.ts`
- Test : `apps/backend/tests/unit/test_passages_candidats.py`

- [ ] **Étape 1 : vérifier deux faits du code.**
  - Qu'un `Chunk` rendu par `app.services.chunker.chunk_text` vérifie
    `texte[c.start:c.end] == c.text` (lire `chunk_text` dans `services/chunker.py`).
    Si le texte est retouché, reconstruire le passage par `texte[c.start:c.end]`.
  - Que `embeddings.embed` rend des vecteurs normés (`tronquer_et_normaliser`) :
    le produit scalaire vaut alors la similarité cosinus.

- [ ] **Étape 2 : écrire les tests qui échouent**

```python
"""Le serveur propose des passages exacts de la page, classes par le sens."""

from __future__ import annotations

import pytest

from app.services import embeddings, passages_candidats
from app.services.passages_candidats import proposer

PAGE = (
    "La taxe carbone suedoise, introduite en 1991, a ete relevee plusieurs fois. "
    "Les emissions du transport ont baisse d'environ 11 % par rapport au scenario sans taxe. "
    "\n\n"
    "Le secteur industriel beneficiait d'exemptions importantes jusqu'en 2018. "
    "Ces exemptions limitaient l'effet de la taxe sur l'industrie lourde."
)


def _vecteur(texte: str) -> list[float]:
    # Deux axes : transport et industrie. Assez pour classer sans reseau.
    t = texte.lower()
    v = [1.0 if "transport" in t else 0.0, 1.0 if "industri" in t else 0.0]
    norme = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norme for x in v]


@pytest.mark.asyncio
async def test_chaque_question_recoit_les_passages_les_plus_proches(monkeypatch):
    async def embed(textes):
        return [_vecteur(t) for t in textes]

    monkeypatch.setattr(embeddings, "embed", embed)
    monkeypatch.setattr(passages_candidats, "TAILLE_PASSAGE", 120)
    candidats = await proposer(PAGE, ["effet sur le transport", "effet sur l'industrie"])

    transport = [c for c in candidats if c.question == "effet sur le transport"]
    industrie = [c for c in candidats if c.question == "effet sur l'industrie"]
    assert transport and "transport" in transport[0].texte
    assert industrie and "industrie" in industrie[0].texte.lower()
    assert all(PAGE[c.debut : c.debut + len(c.texte)] == c.texte for c in candidats)
    assert {c.methode for c in candidats} == {"sens"}


@pytest.mark.asyncio
async def test_sans_embeddings_le_classement_par_mots_prend_le_relais(monkeypatch):
    async def embed(textes):
        return None

    monkeypatch.setattr(embeddings, "embed", embed)
    candidats = await proposer(PAGE, ["exemptions industrie lourde taxe"])
    assert candidats and candidats[0].methode == "mots"
    assert candidats[0].texte in PAGE


@pytest.mark.asyncio
async def test_une_page_vide_ne_propose_rien():
    assert await proposer("", ["n'importe quoi"]) == []
```

- [ ] **Étape 3 : lancer les tests.** Attendu : échec à l'import.

- [ ] **Étape 4 : implémenter `services/passages_candidats.py`**

```python
"""Des passages exacts de la page, classes par le sens pour chaque question.

Mesure du 2026-09-13 : 79 extraits refuses sur 83 avec un modele de 8
milliards de parametres, qui recopiait mal ou reformulait. Ici le serveur
decoupe la page et rend, pour chaque question, les passages les plus proches
par le sens. Le modele ne recopie plus : il choisit. Chaque passage rendu est
une tranche exacte de la page, donc `add_excerpt` l'accepte tel quel.

Sans service d'embeddings (developpement, panne), le classement par mots
communs de `passages_proches` prend le relais : moins fin, jamais vide a tort.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services import embeddings
from app.services.chunker import Unite, chunk_text
from app.services.excerpt_insertion import passages_proches

#: Taille d'un passage candidat. Meme ordre que la longueur indicative d'un
#: extrait qui porte un raisonnement, dans les principes editoriaux (80 a 160
#: mots, 1 000 caracteres au plus).
TAILLE_PASSAGE = 700

#: Proximite de sens en dessous de laquelle un passage ne repond pas a la
#: question. Seuil mesure en production pour la recherche d'extraits par le sens.
SEUIL_SENS = 0.60

#: Passages rendus par question. Borne de lisibilite de la reponse d'outil, pas
#: une borne editoriale : une page dense se reinterroge avec d'autres questions.
PASSAGES_PAR_QUESTION = 8


@dataclass(frozen=True)
class Candidat:
    question: str
    texte: str
    debut: int
    score: float
    methode: str


def _similarite(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def proposer(
    page_text: str, questions: list[str], par_question: int = PASSAGES_PAR_QUESTION
) -> list[Candidat]:
    questions = [q.strip() for q in questions if q and q.strip()]
    if not page_text.strip() or not questions:
        return []
    morceaux = [m for m in chunk_text(page_text, TAILLE_PASSAGE, Unite.CARACTERES) if m.text.strip()]
    if not morceaux:
        return []
    vecteurs = await embeddings.embed([m.text for m in morceaux] + questions)
    if vecteurs is None:
        rendus: list[Candidat] = []
        for question in questions:
            for passage in passages_proches(page_text, question, limite=par_question):
                rendus.append(Candidat(question, passage, page_text.find(passage), 0.0, "mots"))
        return rendus

    passages, cibles = vecteurs[: len(morceaux)], vecteurs[len(morceaux) :]
    rendus = []
    for question, cible in zip(questions, cibles, strict=True):
        notes = sorted(
            ((_similarite(v, cible), m) for v, m in zip(passages, morceaux, strict=True)),
            key=lambda note: note[0],
            reverse=True,
        )
        for score, morceau in notes[:par_question]:
            if score < SEUIL_SENS:
                break
            texte = page_text[morceau.start : morceau.end].strip()
            debut = page_text.find(texte, morceau.start)
            rendus.append(Candidat(question, texte, debut, round(score, 3), "sens"))
    return rendus
```

- [ ] **Étape 5 : lancer les tests.** Attendu : vert. Si le test « par le sens »
  échoue sur le seuil, c'est que `_vecteur` rend 0,707 pour un passage à deux
  axes : c'est voulu, 0,707 dépasse 0,60.

- [ ] **Étape 6 : l'outil `propose_passages` dans `tools_write.py`**, après
  `find_passage` :

```python
async def propose_passages(
    db: AsyncSession,
    user: User,
    *,
    url: str,
    questions: list[str],
) -> dict[str, Any]:
    """Propose, pour chaque question, les passages exacts de la page les plus proches par le sens.

    A appeler sur une adresse candidate AVANT de l'ajouter comme source. Chaque
    passage rendu est une tranche exacte de la page : retiens ceux qui repondent
    vraiment, et passe-les tels quels dans `add_source(..., excerpts=[...])`.
    `questions` : la question de la fiche, ou ses sous-questions. Ne pose rien.
    """
    from app.services import excerpt_insertion
    from app.services.passages_candidats import proposer

    adresse = (url or "").strip()
    if not adresse:
        raise ToolError("Une adresse est requise.")
    page_text, _refuse, complet = await excerpt_insertion.texte_de_page(adresse)
    if not page_text.strip():
        raise ToolError(
            "Le texte de cette page n'a pu etre obtenu par aucune voie : cette "
            "candidate ne peut pas porter d'extrait. Passe a la suivante."
        )
    candidats = await proposer(page_text, questions)
    resultat: dict[str, Any] = {
        "url": adresse,
        "texte_complet": complet,
        "passages": [
            {"question": c.question, "texte": c.texte, "score": c.score} for c in candidats
        ],
    }
    if not candidats:
        resultat["message"] = (
            "Aucun passage de cette page ne repond aux questions : n'ajoute pas cette "
            "source, passe a la candidate suivante."
        )
    return resultat
```

- [ ] **Étape 7 : exposer l'outil.**
  - `philum.py`, `_ECRITURE` : ajouter `"propose_passages"` après `"find_passage"`.
  - `services/agent.py`, `LECTURES_REPRISES` : ajouter `"propose_passages"`
    (lecture sans écriture, rejouable depuis le cache).
  - `server.py`, avant `suggest_excerpts` :

```python
@outil()
async def propose_passages(url: str, questions: list[str]) -> dict[str, Any]:
    """Propose, pour chaque question, les passages exacts d'une page les plus
    proches par le sens, prets a citer."""
    async with _session() as db:
        user = await exiger_utilisateur(db)
        return await tools_write.propose_passages(db, user, url=url, questions=questions)
```

  - `toolLabels.ts`, après `find_passage` :

```ts
  propose_passages: {
    action: 'Cherche les passages utiles dans',
    objet: (a) => (typeof a.url === 'string' ? a.url : 'une page'),
  },
```

- [ ] **Étape 8 : tester l'outil.** Ajouter à `test_passages_candidats.py` :

```python
from app.mcp_server.tools_write import propose_passages
from app.services import excerpt_insertion


@pytest.mark.asyncio
async def test_l_outil_rend_les_passages_et_dit_quand_rien_ne_repond(
    db_session, test_user, monkeypatch
):
    async def page(url):
        return PAGE, False, True

    async def embed(textes):
        return [_vecteur(t) for t in textes]

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", page)
    monkeypatch.setattr(embeddings, "embed", embed)
    monkeypatch.setattr(passages_candidats, "TAILLE_PASSAGE", 120)

    rendu = await propose_passages(
        db_session, test_user, url="https://exemple.test/taxe", questions=["transport"]
    )
    assert rendu["passages"] and "transport" in rendu["passages"][0]["texte"]

    vide = await propose_passages(
        db_session, test_user, url="https://exemple.test/taxe", questions=["volcanologie"]
    )
    assert vide["passages"] == [] and "passe a la candidate suivante" in vide["message"]
```

- [ ] **Étape 9 : suite complète backend, tests front des libellés**
  (`npx vitest run src/tests/agent-tool-labels.test.ts`), lint, types.
- [ ] **Étape 10 : commit, PR.** Titre : `feat(agent): le serveur propose des passages exacts classes par le sens`.

**Critère d'acceptation :** en prod, `propose_passages` sur une page lisible rend
des passages que `add_source(..., excerpts=...)` accepte sans refus.

---

## PR 3 : exploration atomique, aucune source sans extrait (B1, B3)

**Pourquoi :** le déroulé ajoute les sources à une étape et cherche leurs extraits
à la suivante ; une source sans passage retrouvé reste vide dans la fiche.

**Files :**
- Modify : `apps/backend/app/agent_tools/philum.py` (garde et nettoyage dans `_execute`)
- Modify : `apps/backend/app/services/deroule_guide.py` (`ETAPES`)
- Modify : `apps/backend/tests/unit/test_deroule_guide.py`
- Test : `apps/backend/tests/unit/test_source_avec_extraits.py`

- [ ] **Étape 1 : vérifier les signatures** de `ecriture._fiche_du_createur(db,
  user, slug)` et `ecriture.delete_source(db, user, *, source_id)` dans
  `tools_write.py`. Si `delete_source` fait plus qu'une suppression douce (effet
  sur le feed, archives), écrire à la place une suppression douce dédiée
  `_retirer_source_vide(db, user, source_id)` qui pose `deleted_at`.

- [ ] **Étape 2 : écrire les tests qui échouent**

```python
"""Pour l'agent, une source n'entre dans une fiche sujet qu'avec ses extraits."""

from __future__ import annotations

import pytest

from app.agent_tools import philum
from app.agent_tools.tool import ToolContext
from app.mcp_server import tools_write
from app.mcp_server.tools_write import create_card, list_sources
from app.services import excerpt_insertion

PAGE = "Les exemptions industrielles ont limite l'effet de la taxe carbone jusqu'en 2018."


@pytest.fixture
def _hors_ligne(monkeypatch):
    async def existe(url, doi):
        return None

    async def page(url):
        return PAGE, False, True

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", existe)
    excerpt_insertion.vider_le_cache()
    monkeypatch.setattr(excerpt_insertion, "texte_de_page", page)


def _outil(nom):
    return next(t for t in philum.philum_tools() if t.name == nom)


async def _ctx(db_session, test_user):
    return ToolContext(db=db_session, user=test_user, creator_id=test_user.id, session_id=None)


@pytest.mark.asyncio
async def test_sans_extrait_la_source_est_refusee_sur_une_fiche_sujet(
    db_session, test_user, _hors_ligne
):
    await create_card(db_session, test_user, slug="taxe", title="Taxe carbone", card_kind="sujet")
    rendu = await _outil("add_source").execute(
        await _ctx(db_session, test_user),
        {"card_slug": "taxe", "metadata_from": "page", "url": "https://exemple.test/a"},
    )
    assert "error" in rendu and "extrait" in rendu["error"]
    assert (await list_sources(db_session, test_user, card_slug="taxe"))["sources"] == []


@pytest.mark.asyncio
async def test_une_source_dont_tous_les_extraits_sont_refuses_est_retiree(
    db_session, test_user, _hors_ligne
):
    await create_card(db_session, test_user, slug="taxe", title="Taxe carbone", card_kind="sujet")
    rendu = await _outil("add_source").execute(
        await _ctx(db_session, test_user),
        {
            "card_slug": "taxe",
            "metadata_from": "page",
            "url": "https://exemple.test/a",
            "excerpts": [{"text": "Une phrase qui ne figure nulle part dans la page."}],
        },
    )
    assert "error" in rendu
    assert (await list_sources(db_session, test_user, card_slug="taxe"))["sources"] == []


@pytest.mark.asyncio
async def test_une_source_avec_un_extrait_retrouve_entre(db_session, test_user, _hors_ligne):
    await create_card(db_session, test_user, slug="taxe", title="Taxe carbone", card_kind="sujet")
    rendu = await _outil("add_source").execute(
        await _ctx(db_session, test_user),
        {
            "card_slug": "taxe",
            "metadata_from": "page",
            "url": "https://exemple.test/a",
            "excerpts": [{"text": PAGE}],
        },
    )
    assert "error" not in rendu and rendu["excerpts"]
```

Adapter la clé `["sources"]` au format réel rendu par `list_sources` (lire sa
docstring) avant de lancer.

- [ ] **Étape 3 : lancer.** Attendu : les deux premiers tests échouent.

- [ ] **Étape 4 : implémenter dans `philum.py`**, avant `_envelopper` :

```python
_SOURCE_SANS_EXTRAIT = (
    "Source non ajoutee : une fiche sujet ne garde que les sources qui portent au "
    "moins un extrait. Cherche d'abord les passages avec propose_passages(url, "
    "questions), puis appelle add_source avec excerpts=[{\"text\": ..., "
    "\"context\": ...}]. Si aucun passage ne repond, passe a la candidate suivante."
)


async def _fiche_sujet(ctx: ToolContext, slug: Any) -> bool:
    try:
        fiche = await ecriture._fiche_du_createur(ctx.db, ctx.user, str(slug or ""))
    except ToolError:
        return False
    return fiche.card_kind == CardKind.SUJET.value


async def _garde_source_sans_extrait(nom: str, ctx: ToolContext, kwargs: dict[str, Any]) -> str | None:
    """Refuse, pour l'agent, une source posee sans extrait sur une fiche sujet.

    Le createur, dans l'interface, n'est pas concerne : il peut poser une source
    a completer plus tard. Seule l'enveloppe de l'agent applique la regle.
    """
    if nom == "add_sources_batch" and await _fiche_sujet(ctx, kwargs.get("card_slug")):
        return _SOURCE_SANS_EXTRAIT
    if nom == "add_source" and not kwargs.get("excerpts") and await _fiche_sujet(ctx, kwargs.get("card_slug")):
        return _SOURCE_SANS_EXTRAIT
    return None
```

Dans `_execute`, juste après `kwargs = _coercer(args, proprietes)` (hors du
`try` de coercition) :

```python
        refus = await _garde_source_sans_extrait(fonction.__name__, ctx, kwargs)
        if refus:
            return {"error": refus}
```

Et après l'appel, avant `return _guider(...)`, retirer la source restée vide :

```python
            if (
                fonction.__name__ == "add_source"
                and isinstance(resultat, dict)
                and resultat.get("id")
                and not resultat.get("excerpts")
                and await _fiche_sujet(ctx, kwargs.get("card_slug"))
            ):
                await ecriture.delete_source(ctx.db, ctx.user, source_id=str(resultat["id"]))
                raisons = "; ".join(r["raison"] for r in resultat.get("excerpts_refuses", []))
                return {"error": f"{_SOURCE_SANS_EXTRAIT} Extraits refuses : {raisons}"}
```

Ajouter `from app.models.biblio_card import CardKind` si absent (il est importé
en tête du fichier).

- [ ] **Étape 5 : lancer les tests.** Attendu : vert.

- [ ] **Étape 6 : fusionner sources et extraits dans le déroulé.** Dans
  `deroule_guide.py`, remplacer les étapes `sources` et `extraits` par :

```python
    Etape(
        id="exploration",
        titre="Exploration",
        outils=("propose_passages", "add_source", "list_sources", "find_passage"),
        consigne=(
            "Pour chaque adresse retenue à l'étape de recherche :\n"
            "1. Appelle propose_passages(url, questions) avec la question du créateur.\n"
            "2. Retiens les passages qui répondent vraiment, et ceux qui nuancent.\n"
            "3. S'il en reste au moins un, appelle add_source(card_slug, url, "
            "metadata_from='page', excerpts=[{\"text\": passage recopié tel quel, "
            "\"context\": ce que le passage établit}]).\n"
            "4. Sinon, n'ajoute pas la source.\n"
            "Termine par deux listes : les sources ajoutées avec leur nombre d'extraits, "
            "et les adresses écartées avec la raison."
        ),
    ),
```

Le déroulé passe à quatre étapes : recherche, exploration, positions, bilan.

- [ ] **Étape 7 : adapter `test_deroule_guide.py`.** Les réponses simulées passent
  de six à cinq (une par étape après l'appel `create_card`), et le registre de
  test ajoute `propose_passages`. L'assertion `etapes == [e.id for e in ETAPES]`
  reste valable.

- [ ] **Étape 8 : ajouter au registre de test** de `test_deroule_guide.py` :

```python
        "propose_passages": _outil("propose_passages", {"passages": []}),
```

- [ ] **Étape 9 : suite complète, lint, types. Commit, PR.** Titre :
  `feat(agent): une source n'entre dans une fiche sujet qu'avec ses extraits`.

**Critère d'acceptation :** au banc, `sources` = `sources_avec_extrait` sur toutes
les demandes (aucune source sans extrait), et `part_extraits_refuses` inférieure
à celle mesurée avant la PR 2.

---

## PR 4 : plan de couverture, rendement, indicateur (A1, D2, D3)

Plan détaillé à écrire au démarrage, dans le format des PR 1 à 3. Contrat fixé ici :

**Files :**
- Create : `apps/backend/app/services/couverture.py`
- Modify : `apps/backend/app/services/deroule_guide.py`
- Modify : `apps/backend/app/api/v1/endpoints/agent_fiche.py` (route de lecture)
- Modify : `apps/frontend/src/lib/components/chat/FicheVivante.svelte`, `src/lib/api/agent.ts`
- Tests : `tests/unit/test_couverture.py`, `tests/unit/test_deroule_guide.py`, `src/tests/agent-couverture.test.ts`

**Interfaces :**

```python
# services/couverture.py
@dataclass(frozen=True)
class SousQuestion:
    texte: str
    extraits: int          # extraits de la fiche rattaches a cette sous-question
    sources: int

@dataclass(frozen=True)
class Couverture:
    slug: str
    sous_questions: list[SousQuestion]
    sources_sans_extrait: int
    candidates_ecartees: int

async def lire_plan(db, creator_id, slug) -> list[str]
    # lit runs/<slug>/plan.md : une sous-question par ligne commencant par "- "

async def ecrire_plan(db, creator_id, slug, sous_questions: list[str]) -> None

async def calculer(db, creator_id, slug) -> Couverture
    # rattache chaque extrait a la sous-question la plus proche par le sens
    # (services/embeddings.embed), repli par mots communs sans embeddings
```

**Déroulé :** une étape `plan` en tête (outil `definir_plan(slug, sous_questions)`
exposé à cette étape seulement, qui appelle `ecrire_plan`). L'exploration tourne
par **passes** : chaque passe cherche sur les sous-questions les moins couvertes
(`calculer`) ; le déroulé enchaîne les passes tant que la dernière a ajouté au
moins un extrait sur une sous-question jusque-là sans extrait, et s'arrête sinon.
Aucun nombre de passes fixé d'avance ; le mur de 20 minutes reste la borne
technique.

**Route :** `GET /agent/fiche/{slug}/couverture` rend `Couverture` en JSON.
**Front :** `FicheVivante` affiche, sous le titre, une ligne par sous-question
(nombre d'extraits, pastille vide si zéro), relue à chaque `empreinte`.

**Tests clés :**
- `test_une_fiche_dont_chaque_sous_question_porte_un_extrait_est_couverte`
- `test_le_deroule_s_arrete_quand_une_passe_n_ajoute_rien`
- `test_le_deroule_relance_une_passe_sur_les_sous_questions_vides`
- un sujet d'économie (« la taxe carbone réduit-elle les émissions ? ») et un
  sujet d'histoire dans les exemples.

**Critère d'acceptation :** au banc, chaque demande rend un plan, et la part de
sous-questions couvertes est chiffrée.

---

## PR 5 : recherche par famille de sources (A2, A3, A4, A5, A6)

Plan détaillé à écrire au démarrage. Contrat fixé ici :

**Files :**
- Create : `apps/backend/app/agent_tools/litterature.py` (outils `search_sources`, `references`)
- Modify : `apps/backend/app/agent_tools/registry.py`, `services/deroule_guide.py`
- Modify : `apps/frontend/src/lib/agent/toolLabels.ts`
- Tests : `tests/unit/test_litterature.py` (réseau simulé par `httpx.MockTransport`)

**Interfaces :**

```python
FAMILLES = ("litterature", "biomedical", "institutions", "presse", "encyclopedie", "video")

async def _execute_search_sources(ctx, args) -> dict
    # args : query (str), familles (list[str], defaut : toutes celles configurees)
    # rend : {"resultats": [{"url", "titre", "famille", "nature", "annee",
    #          "doi", "texte_integral_url", "resume"}], "familles_interrogees": [...]}

async def _execute_references(ctx, args) -> dict
    # args : doi (str) ou url (str), sens ("cite" | "cite_par")
    # rend : {"resultats": [...meme forme...]}
```

**Familles et fournisseurs :**

| Famille | Fournisseur | Nature lue |
|---|---|---|
| `litterature` | OpenAlex `/works?search=` (clé de la PR 1) | `type`, `publication_year`, `open_access.oa_url` |
| `biomedical` | Europe PMC `/search?query=...&format=json` | `pubTypeList`, `fullTextUrlList`, `isOpenAccess` |
| `institutions`, `presse` | recherche web existante, domaines filtrés par famille | domaine |
| `encyclopedie` | API MediaWiki : références de l'article | « encyclopédie », puis nature de chaque référence |
| `video` | `get_youtube_transcript` exposé à l'agent | « transcription » |

**Nature et solidité (A5) :** fonction pure `nature_et_rang(resultat) -> tuple[str, int]`
selon le tableau de la spécification ; le déroulé trie les candidates par rang
avant l'exploration, sans en exclure aucune.
**Texte intégral (A4) :** `texte_integral_url` sert d'adresse d'exploration
quand elle existe.
**Corpus Philum (A6) :** l'étape recherche appelle d'abord `search_cards` et
`search_my_excerpts` ; une source déjà ancrée ailleurs devient candidate prioritaire.
**Références (A3) :** OpenAlex `referenced_works` et `cites:` ; pour une page
web, `import_from_content_url` et `parse_biblio`.

**Vérification périssable au démarrage :** paramètres et quotas actuels
d'OpenAlex, d'Europe PMC et de l'API MediaWiki (documentation officielle), et
exposition de `get_youtube_transcript` au registre de l'agent.

**Tests clés :**
- `test_chaque_resultat_dit_sa_famille_et_sa_nature`
- `test_une_famille_en_panne_n_empeche_pas_les_autres`
- `test_les_candidates_sont_triees_par_solidite_sans_exclusion`
- `test_les_references_d_un_doi_deviennent_des_candidates`
- exemples en droit (décision de justice), histoire (source primaire), économie.

**Critère d'acceptation :** au banc, les candidates explorées couvrent au moins
deux familles par demande quand le sujet s'y prête, et le nombre d'extraits
pertinents par fiche augmente par rapport à la PR 4.

---

## PR 6 : relecteur, extraction exhaustive, nuance par source (D1, B4, B5)

Plan détaillé à écrire au démarrage. Contrat fixé ici :

**Files :**
- Create : `apps/backend/app/services/relecture.py`
- Modify : `apps/backend/app/services/deroule_guide.py`, `app/services/passages_candidats.py`
- Tests : `tests/unit/test_relecture.py`, `tests/unit/test_deroule_guide.py`

**Interfaces :**

```python
@dataclass(frozen=True)
class Manque:
    genre: str       # "sous_question_vide" | "source_sans_extrait" | "position_sans_appui"
                     # | "sans_nuance" | "une_seule_famille" | "retractation"
    cible: str       # sous-question, source_id ou slug
    etape: str       # etape du deroule qui le comble : "exploration" | "positions" | "recherche"

async def grille(db, creator_id, slug) -> list[Manque]
```

**Déroulé :** après `positions`, `grille` est calculée ; chaque manque renvoie à
son étape avec une consigne ciblée ; la boucle s'arrête quand une relecture ne
trouve plus de manque comblable ou qu'une passe n'a rien comblé.
**Extraction exhaustive (B4) :** une candidate dont `propose_passages` rend des
passages au-dessus du seuil pour la majorité des sous-questions passe en
extraction exhaustive : `proposer(..., par_question=len(morceaux))`, redites
exclues.
**Nuance (B5) :** `propose_passages` reçoit, en plus des sous-questions, une
question de réserve formulée à partir de la question du créateur (« limites,
réserves ou résultats contraires sur … »).
**Rétractations :** réutiliser la vérification existante (PR « sources
rétractation périmée »), sans nouveau code réseau.

**Tests clés :**
- `test_une_source_sans_extrait_est_un_manque_renvoye_a_l_exploration`
- `test_la_boucle_s_arrete_quand_une_passe_ne_comble_rien`
- `test_une_source_dense_passe_en_extraction_exhaustive_sans_redite`

**Critère d'acceptation :** au banc, `positions_sans_extrait` = 0 et chaque fiche
porte au moins un extrait de nuance, ou un manque « sans nuance » déclaré.

---

## PR 7 : synthèse ancrée, annotation, mise en situation, redites, pivots (C1, C2, C3, B6, B7)

Plan détaillé à écrire au démarrage. Contrat fixé ici :

**Files :**
- Create : `apps/backend/app/services/synthese.py`
- Modify : `apps/backend/app/services/deroule_guide.py`, `app/mcp_server/tools_write.py`
  (`add_excerpt` : redites et langue), `app/services/fidelite.py` (annotation)
- Modify : front de la fiche publique pour afficher la synthèse et ses renvois
- Tests : `tests/unit/test_synthese.py`, `tests/unit/test_excerpt_insertion.py`

**Interfaces :**

```python
@dataclass(frozen=True)
class PhraseAncree:
    texte: str
    extraits: list[str]      # identifiants d'extraits de la fiche

def decouper_synthese(texte: str) -> list[PhraseAncree]
    # une phrase se termine par [extrait:<uuid>] (un ou plusieurs)

async def verifier(db, creator_id, slug, texte: str) -> list[str]
    # rend les problemes : phrase sans renvoi, renvoi inconnu, renvoi hors fiche
```

**Synthèse (C2) :** l'étape bilan écrit une synthèse par sous-question, vérifiée
par `verifier` avant d'être posée (champ de description ou texte de la fiche
selon le type de fiche, à trancher dans le plan détaillé avec le modèle de
données) ; une synthèse rejetée revient au modèle avec la liste des problèmes.
**Annotation structurée (C1) :** gabarit « apport, nature, méthode, limites,
date », vérifié par le juge de fidélité existant.
**Mise en situation (B6) :** `add_excerpt` exige `context` quand la langue de
l'extrait diffère de celle de la fiche (détection légère par mots fréquents,
sans dépendance lourde).
**Redites (B7) :** `add_excerpt` refuse un extrait dont la similarité de sens
avec un extrait de la même fiche dépasse un seuil mesuré au banc.
**Pivots et connexions (C3) :** l'étape positions marque pivot la source la plus
solide de chaque sous-question ; une étape de connexions reprend la logique de
l'étage 05 (`find_cards_citing`, `list_connections`).

**Tests clés :**
- `test_une_phrase_sans_renvoi_fait_rejeter_la_synthese`
- `test_un_renvoi_vers_un_extrait_d_une_autre_fiche_est_refuse`
- `test_un_extrait_en_anglais_sans_mise_en_situation_est_refuse_sur_une_fiche_francaise`
- `test_un_extrait_quasi_identique_a_un_extrait_pose_est_refuse`

**Critère d'acceptation :** au banc, zéro phrase de synthèse sans renvoi, et zéro
redite sous le seuil retenu.

---

## PR 8 : banc élargi et routage par étape (F, E)

Plan détaillé à écrire au démarrage. Contrat fixé ici :

**Files :**
- Modify : `apps/backend/app/scripts/banc_agent.py`, `tests/unit/test_banc_agent.py`
- Modify : `apps/backend/app/services/deroule_guide.py` (routage)
- Modify : `apps/backend/app/api/v1/endpoints/agent_chat.py` (passer les clés disponibles)

**Banc :**
- `QUESTIONS` passe à au moins deux demandes par terrain : santé, science,
  histoire, économie, droit, technique, culture, actualité.
- Chiffres ajoutés : extraits par fiche, candidates explorées et écartées,
  couverture du plan (PR 4), familles de sources (PR 5), phrases sans renvoi (PR 7).
- Comparaison : `--comparer <fichier.json>` affiche l'écart avec un run précédent.

**Routage (E) :**

```python
def modele_pour_etape(etape: str, candidats: list[AgentProvider]) -> AgentProvider
    # exploration, sources : le modele le plus econome disponible
    # plan, synthese, relecture : le plus capable disponible (profil grand d'abord)
```

Une seule clé disponible : elle sert toutes les étapes, comportement actuel.

**Tests clés :**
- `test_les_questions_couvrent_chaque_terrain`
- `test_la_comparaison_affiche_l_ecart_par_chiffre`
- `test_la_synthese_va_au_modele_le_plus_capable`

**Critère d'acceptation :** un run complet sur un petit et un grand modèle,
publié dans la PR avec son tableau de comparaison.

---

## Couverture de la spécification

| Section | PR |
|---|---|
| A1 plan de couverture | 4 |
| A2 recherche par famille, clé OpenAlex | 1, 5 |
| A3 suivre les références | 5 |
| A4 texte intégral d'abord | 5 |
| A5 nature et solidité | 5 |
| A6 corpus Philum | 5 |
| B1 aucune source sans extrait | 3 |
| B2 passages proposés | 2 |
| B3 une passe par source | 3 (candidate par candidate), 4 (passes) |
| B4 extraction exhaustive | 6 |
| B5 nuance par source | 6 |
| B6 mise en situation | 7 |
| B7 redites | 7 |
| C1 annotation structurée | 7 |
| C2 synthèse ancrée | 7 |
| C3 pivots et connexions | 7 |
| D1 relecteur | 6 |
| D2 borne par rendement | 4 |
| D3 indicateur de couverture | 4 |
| E adapter au modèle, routage | 3 (passages proposés à tous), 8 |
| F mesurer | 8, et un run du banc après chaque PR |
