"""Sur combien de sites la suggestion de citations n'a-t-elle aucun texte ?

`suggest_source_excerpts` lit `page_text` via `_html_scrape` et rend un `422
no_text` quand la page ne se laisse pas lire. L'exigence est que la suggestion
fonctionne *aussi* derriere un anti-crawler ; avant de construire un repli, il
faut savoir sur quelle proportion il mord et ce que chaque repli rattrape.

Ce script ne mesure qu'une chose par URL : la longueur du texte obtenu, par la
voie directe puis par la capture Wayback. Il n'ecrit rien.

Usage : CI=true PYTHONPATH=. uv run python scripts/probe_excerpt_text.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("database_url", "sqlite+aiosqlite:///./probe.db")
os.environ.setdefault("session_secret", "probe-secret-for-local-run-32chars")
os.environ.setdefault("master_encryption_key", "probe-key-for-local-run-32bytes")
os.environ.setdefault("google_client_id", "probe.apps.googleusercontent.com")
os.environ.setdefault("google_client_secret", "probe-secret")
os.environ.setdefault("google_redirect_uri", "http://localhost/api/v1/auth/google/callback")
os.environ.setdefault("ci", "true")

from app.core.config import Settings, get_settings  # noqa: E402

Settings.model_config["case_sensitive"] = False
get_settings.cache_clear()

from app.extractors.url_extractor import _html_scrape  # noqa: E402

# Un echantillon volontairement hostile : les quatre personas de l'audit, plus
# les sites dont le projet sait deja qu'ils refusent la visite.
URLS = [
    "https://www.propublica.org/article/how-the-irs-was-gutted",
    "https://www.youtube.com/watch?v=aircAruvnKk",
    "https://gwern.net/scaling-hypothesis",
    "https://www.who.int/news-room/fact-sheets/detail/depression",
    "https://www.nytimes.com/2024/01/01/technology/ai-chatbots.html",
    "https://www.lemonde.fr/sciences/article/2024/01/10/intelligence-artificielle_1.html",
    "https://www.sciencedirect.com/science/article/pii/S0092867420301021",
    "https://www.treasury.gov/",
    "https://www.nature.com/articles/s41586-021-03819-2",
    "https://www.cell.com/cell/fulltext/S0092-8674(20)30102-1",
]

SEUIL = 500  # en deca, il n'y a pas de quoi decouper un extrait


async def sonde(url: str) -> None:
    try:
        meta = await _html_scrape(url)
    except Exception as exc:  # noqa: BLE001 - on veut le verdict, pas le crash
        print(f"  {url}\n    ECHEC {type(exc).__name__}: {exc}")
        return
    texte = (getattr(meta, "page_text", None) or "") if meta else ""
    verdict = "OK" if len(texte) >= SEUIL else "INSUFFISANT"
    print(f"  [{verdict:11}] {len(texte):>7} car.  {url}")


async def main() -> None:
    print(f"Texte lisible par _html_scrape (seuil {SEUIL} caracteres)\n")
    for url in URLS:
        await sonde(url)


if __name__ == "__main__":
    asyncio.run(main())
