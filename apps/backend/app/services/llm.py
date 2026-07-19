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
