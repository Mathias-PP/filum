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


def _response_schema() -> dict:
    schema = LlmSourceMetadata.model_json_schema()
    return {
        "type": "json_schema",
        "json_schema": {"name": "source_metadata", "schema": schema},
    }


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

    payload = {
        "model": "biblio-parse",
        "messages": [
            {"role": "system", "content": _REF_BLOCK_SYSTEM_PROMPT},
            {"role": "user", "content": block},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "biblio_ref", "schema": LlmBiblioRef.model_json_schema()},
        },
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.litellm_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
        if r.status_code != 200:
            logger.warning("LLM ref-block HTTP %s: %s", r.status_code, r.text[:200])
            return None
        content = r.json()["choices"][0]["message"]["content"]
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
    except Exception as e:
        logger.warning("LLM ref-block failed: %s", e)
        return None


async def parse_bibliography(text: str) -> list[LlmBiblioRef] | None:
    """Extrait les références via l'alias `biblio-parse`. Never raises.

    Retourne None si la couche LLM est désactivée ou en cas d'erreur —
    l'appelant garde le résultat du parsing déterministe.
    """
    settings = get_settings()
    if not settings.litellm_base_url:
        return None

    payload = {
        "model": "biblio-parse",
        "messages": [
            {"role": "system", "content": _BIBLIO_SYSTEM_PROMPT},
            {"role": "user", "content": text[:_MAX_INPUT_CHARS]},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "biblio_refs", "schema": LlmBiblioRefs.model_json_schema()},
        },
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.litellm_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
        if r.status_code != 200:
            logger.warning("LLM biblio-parse HTTP %s: %s", r.status_code, r.text[:200])
            return None
        content = r.json()["choices"][0]["message"]["content"]
        return parse_biblio_content(content)
    except Exception as e:
        logger.warning("LLM biblio-parse failed: %s", e)
        return None


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
    settings = get_settings()
    payload = {
        "model": "biblio-parse",
        "messages": [
            {"role": "system", "content": _TRANSCRIPT_SYSTEM_PROMPT},
            {"role": "user", "content": text[:_MAX_INPUT_CHARS]},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "biblio_refs", "schema": LlmBiblioRefs.model_json_schema()},
        },
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.litellm_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
        if r.status_code != 200:
            logger.warning("LLM transcript HTTP %s: %s", r.status_code, r.text[:200])
            return None
        return parse_biblio_content(r.json()["choices"][0]["message"]["content"])
    except Exception as e:
        logger.warning("LLM transcript failed: %s", e)
        return None


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

    payload = {
        "model": "excerpt-suggest",
        "messages": [
            {"role": "system", "content": _EXCERPT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "excerpts", "schema": LlmExcerpts.model_json_schema()},
        },
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.litellm_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
        if r.status_code != 200:
            logger.warning("LLM excerpt-suggest HTTP %s: %s", r.status_code, r.text[:200])
            return None
        content = r.json()["choices"][0]["message"]["content"]
        return parse_excerpts_content(content)
    except Exception as e:
        logger.warning("LLM excerpt-suggest failed: %s", e)
        return None


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
    payload = {
        "model": "excerpt-suggest",
        "messages": [
            {"role": "system", "content": _CHUNK_TITLE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "titles", "schema": LlmChunkTitles.model_json_schema()},
        },
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.litellm_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
        if r.status_code != 200:
            logger.warning("LLM chunk-titles HTTP %s: %s", r.status_code, r.text[:200])
            return None
        content = r.json()["choices"][0]["message"]["content"]
        return normalize_chunk_titles(LlmChunkTitles.model_validate_json(content).titles, chunks)
    except Exception as e:
        logger.warning("LLM chunk-titles failed: %s", e)
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

    payload = {
        "model": "biblio-parse",
        "messages": [
            {"role": "system", "content": _URL_CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "url_classification",
                "schema": LlmUrlClassification.model_json_schema(),
            },
        },
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.litellm_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
        if r.status_code != 200:
            logger.warning("LLM classify-url HTTP %s: %s", r.status_code, r.text[:200])
            return None
        content = r.json()["choices"][0]["message"]["content"]
        try:
            parsed = LlmUrlClassification.model_validate_json(content)
        except ValidationError:
            return None
        t = parsed.type.lower().strip()
        if t in ("source", "promo", "social", "other"):
            return t
        return None
    except Exception as e:
        logger.warning("LLM classify-url failed: %s", e)
        return None


async def extract_metadata(page_text: str, url: str) -> LlmSourceMetadata | None:
    """Extrait les métadonnées via l'alias `metadata-extract`. Never raises.

    Retourne None si la couche LLM est désactivée ou en cas d'erreur —
    l'appelant (extracteur heuristique) reste la source de vérité.
    """
    settings = get_settings()
    if not settings.litellm_base_url:
        return None

    payload = {
        "model": "metadata-extract",
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"URL : {url}\n\nContenu de la page :\n{page_text[:_MAX_INPUT_CHARS]}",
            },
        ],
        "response_format": _response_schema(),
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.litellm_base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
        if r.status_code != 200:
            logger.warning("LLM metadata-extract HTTP %s: %s", r.status_code, r.text[:200])
            return None
        content = r.json()["choices"][0]["message"]["content"]
        return parse_metadata_content(content)
    except Exception as e:
        logger.warning("LLM metadata-extract failed for url=%s: %s", url, e)
        return None
