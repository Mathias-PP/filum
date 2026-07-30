"""Oracle YouTube : la bibliographie d'une video vit dans sa description.

Etage 1 du pipeline d'extraction. Le HTML rendu de youtube.com ne contient
que la description tronquee ("...plus"), mais la page embarque le texte
integral en JSON dans ``ytInitialPlayerResponse.videoDetails.shortDescription``.
On lit ce champ, sans API key ni navigateur headless.

La description n'est pas une section References normee : on ne peut pas la
parser comme une biblio scholarly. On retourne donc le texte brut, que le
pipeline traite comme n'importe quel corpus (regex URLs + LLM), avec la
garantie que le perimetre est bien "ce que le createur a lui-meme liste".
"""

from __future__ import annotations

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

_YOUTUBE_HOST_RE = re.compile(
    r"^(?:https?://)?(?:[\w-]+\.)*(?:youtube\.com|youtube-nocookie\.com|youtu\.be)(?:/|$)",
    re.IGNORECASE,
)

# La page injecte `var ytInitialPlayerResponse = {...};` (parfois sans `var`).
# On capture a partir de l'accolade et on laisse JSONDecoder trouver la fin :
# la description contient des accolades/guillemets echappes qui rendent toute
# regex de fermeture non fiable.
_PLAYER_RESPONSE_RE = re.compile(r"ytInitialPlayerResponse\s*=\s*")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
_TIMEOUT = httpx.Timeout(15.0)


def is_youtube_url(url: str) -> bool:
    """True pour une URL YouTube (watch, short, youtu.be, nocookie)."""
    if not url:
        return False
    return bool(_YOUTUBE_HOST_RE.match(url.strip()))


def _extract_player_response(html: str) -> dict | None:
    """Extrait l'objet JSON ytInitialPlayerResponse du HTML de la page."""
    m = _PLAYER_RESPONSE_RE.search(html)
    if not m:
        return None
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(html[m.end() :])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def extract_description_from_html(html: str) -> str | None:
    """Description integrale depuis le HTML d'une page video. None si absente."""
    player = _extract_player_response(html)
    if not player:
        return None
    details = player.get("videoDetails")
    if not isinstance(details, dict):
        return None
    description = details.get("shortDescription")
    if not isinstance(description, str):
        return None
    description = description.strip()
    return description or None


async def fetch_youtube_description(url: str) -> str | None:
    """Telecharge la page video et retourne sa description integrale."""
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            response = await client.get(url)
    except httpx.HTTPError as e:
        logger.warning("youtube_oracle fetch failed url=%s err=%s", url, e)
        return None
    if response.status_code != 200:
        logger.warning("youtube_oracle http=%d url=%s", response.status_code, url)
        return None
    return extract_description_from_html(response.text)
