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

import asyncio
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


def extract_channel_name_from_html(html: str) -> str | None:
    """Nom de la chaine, depuis ``videoDetails.author``. None si absent."""
    player = _extract_player_response(html)
    if not player:
        return None
    details = player.get("videoDetails")
    if not isinstance(details, dict):
        return None
    author = details.get("author")
    if not isinstance(author, str):
        return None
    return author.strip() or None


# En deca de cette longueur, le nom de chaine est un mot trop commun pour
# servir de signal : « Vox » apparait dans voxeurop.eu, et filtrer dessus
# emporterait de vraies sources.
_CHANNEL_NAME_MIN_LEN = 6


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def is_creator_self_link(url: str, title: str | None, channel_name: str | None) -> bool:
    """True si le lien pointe vers une propriete de l'auteur·ice de la video.

    La fin d'une description YouTube est un bloc de signature — Patreon, site
    perso, comptes sociaux, boutique — reconduit a l'identique d'une video a
    l'autre. Mesure du 2026-08-07 : 11 des 16 sources extraites d'une video
    3Blue1Brown en venaient. Ce bloc ne dit rien de ce sur quoi cette video-la
    s'appuie, et il noie les quelques vraies sources.

    On teste le nom de chaine dans l'URL et dans le titre du lien : l'album de
    la bande-son a une URL Spotify opaque que seul son titre trahit.

    Effet de bord accepte : un article tiers qui parle de l'auteur·ice et porte
    son nom serait ecarte. C'est rare, et la fiche reste editable a l'ecran.
    """
    if not channel_name:
        return False  # sans savoir a qui est la chaine, tout filtrage est arbitraire
    needle = _squash(channel_name)
    if len(needle) < _CHANNEL_NAME_MIN_LEN:
        return False
    return needle in _squash(url) or (bool(title) and needle in _squash(title or ""))


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


def parse_json3_transcript(payload: str) -> str | None:
    """Aplatit une piste de sous-titres au format json3 en texte continu.

    json3 plutot que vtt : les pistes automatiques en vtt repetent chaque
    ligne dans la fenetre glissante suivante, ce qui triple le texte.
    """
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    parts: list[str] = []
    for event in data.get("events") or []:
        if not isinstance(event, dict):
            continue
        for seg in event.get("segs") or []:
            if isinstance(seg, dict) and isinstance(seg.get("utf8"), str):
                parts.append(seg["utf8"])
    text = re.sub(r"\s+", " ", "".join(parts)).strip()
    return text or None


def pick_subtitle_track(info: dict) -> tuple[str, str] | None:
    """(langue, url json3) de la meilleure piste. None si aucune.

    Priorite : sous-titres rediges par le createur avant sous-titres
    automatiques (l'ASR se trompe sur les noms propres, precisement ce qui
    nous interesse). Dans chaque categorie, la langue de la video d'abord,
    puis fr/en, puis n'importe laquelle : le pipeline doit rester agnostique
    a la langue du contenu.
    """
    video_lang = info.get("language")
    preferred = [lang for lang in (video_lang, "fr", "en") if isinstance(lang, str)]
    for key in ("subtitles", "automatic_captions"):
        tracks = info.get(key)
        if not isinstance(tracks, dict) or not tracks:
            continue
        ordered = [lang for lang in preferred if lang in tracks]
        ordered += [lang for lang in sorted(tracks) if lang not in ordered]
        for lang in ordered:
            for fmt in tracks[lang] or []:
                if isinstance(fmt, dict) and fmt.get("ext") == "json3" and fmt.get("url"):
                    return lang, fmt["url"]
    return None


def _probe_video(url: str) -> dict | None:
    """Metadonnees yt-dlp, sans telechargement. Appel bloquant."""
    from yt_dlp import YoutubeDL

    options = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 20,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    return info if isinstance(info, dict) else None


async def fetch_youtube_transcript(url: str) -> str | None:
    """Transcription de la video. None si aucune piste exploitable.

    Canal separe de la description : l'ASR est trop bruite (noms propres
    massacres) pour alimenter la liste de references, il ne sert qu'a
    proposer des suggestions que l'utilisateur valide explicitement.
    """
    try:
        info = await asyncio.to_thread(_probe_video, url)
    except Exception as e:
        logger.warning("youtube_transcript probe failed url=%s err=%s", url, e)
        return None
    if not info:
        return None
    track = pick_subtitle_track(info)
    if not track:
        logger.info("youtube_transcript no_track url=%s", url)
        return None
    lang, track_url = track
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            response = await client.get(track_url)
    except httpx.HTTPError as e:
        logger.warning("youtube_transcript fetch failed url=%s err=%s", url, e)
        return None
    if response.status_code != 200:
        logger.warning("youtube_transcript http=%d url=%s", response.status_code, url)
        return None
    text = parse_json3_transcript(response.text)
    if text:
        logger.info("youtube_transcript hit url=%s lang=%s chars=%d", url, lang, len(text))
    return text


async def fetch_youtube_description(url: str) -> tuple[str | None, str | None]:
    """Telecharge la page video : (description integrale, nom de chaine).

    Les deux viennent du meme objet JSON, d'ou un seul telechargement.
    """
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            response = await client.get(url)
    except httpx.HTTPError as e:
        logger.warning("youtube_oracle fetch failed url=%s err=%s", url, e)
        return None, None
    if response.status_code != 200:
        logger.warning("youtube_oracle http=%d url=%s", response.status_code, url)
        return None, None
    return extract_description_from_html(response.text), extract_channel_name_from_html(
        response.text
    )
