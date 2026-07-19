"""Unique point de contact LLM du backend (via le proxy LiteLLM).

Le backend n'appelle jamais un provider directement : il parle à LiteLLM
(`litellm_base_url`) avec un alias de tâche comme nom de modèle
(cf. .docs/17-llm-strategy.md). Si `litellm_base_url` est vide, toute la
couche LLM est désactivée et les appels retournent None — l'application
fonctionne à l'identique sans proxy (dev local, CI, Railway historique).
"""

from __future__ import annotations

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
