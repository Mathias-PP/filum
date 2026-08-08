"""Les sources qui restent sans titre : sont-elles recuperables ?

#327 a cesse d'accepter comme titre une ancre qui n'en est pas — un morceau de
phrase souligne n'est pas le nom d'un document, et un titre faux se recopie
dans la fiche sans que rien ne signale qu'il ne designe pas ce qu'il pretend.
Le prix de cette rigueur se mesure : le re-audit du 2026-08-08 compte 8 sources
sans titre sur l'essai gwern, la ou le compte etait de zero avant.

Zero titre faux, mais huit URLs nues. Reste a savoir si ces huit sont sans
titre parce que leur page n'en donne pas — auquel cas il n'y a rien a faire et
l'URL nue est la reponse honnete — ou parce que le pipeline ne le leur a pas
demande. Le second cas serait un vrai defaut : `_backfill_url_metadata` plafonne
a 60 visites (`_URL_BACKFILL_MAX`), et l'essai porte 78 references.

Le script fait tourner le pipeline, liste les refs restees sans titre, puis
redemande a chacune de ces pages son titre, une par une et sans plafond. L'ecart
entre les deux repond a la question.

Usage : CI=true uv run python scripts/probe_titres_manquants.py [persona]
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("database_url", "sqlite+aiosqlite:///./probe_titres.db")
os.environ.setdefault("session_secret", "probe-secret-for-local-run-32chars")
os.environ.setdefault("master_encryption_key", "probe-key-for-local-run-32bytes")
os.environ.setdefault("google_client_id", "probe.apps.googleusercontent.com")
os.environ.setdefault("google_client_secret", "probe-secret")
os.environ.setdefault("google_redirect_uri", "http://localhost/api/v1/auth/google/callback")
os.environ.setdefault("ci", "true")

from app.core.config import Settings, get_settings  # noqa: E402

Settings.model_config["case_sensitive"] = False
get_settings.cache_clear()

from app.api.v1.endpoints.imports import (  # noqa: E402
    ImportFromUrlRequest,
    parse_content_url,
)
from app.extractors.url_extractor import extract  # noqa: E402

# Le pipeline dit lui-meme, en INFO, combien de candidats son plafond ecarte.
logging.basicConfig(level=logging.INFO, format="  [log] %(message)s")

PERSONAS: dict[str, str] = {
    "journaliste": "https://www.propublica.org/article/how-the-irs-was-gutted",
    "vulgarisateur": "https://www.youtube.com/watch?v=aircAruvnKk",
    "essayiste": "https://gwern.net/scaling-hypothesis",
    "institution": "https://www.who.int/news-room/fact-sheets/detail/depression",
}


class _FakeRequest:
    """`parse_content_url` ne lit la requete que pour le rate-limit, retire."""

    client = None
    headers: dict[str, str] = {}


async def _titre_de_la_page(url: str) -> str | None:
    """Ce que la page repond quand on lui demande son titre, sans plafond."""
    try:
        meta = await asyncio.wait_for(extract(url), timeout=30)
    except Exception as e:  # noqa: BLE001 - une sonde ne doit jamais s'interrompre
        print(f"      erreur : {type(e).__name__}: {e}")
        return None
    return meta.title if meta else None


async def sonder(nom: str, url: str) -> None:
    print("=" * 72)
    print(f"{nom.upper()} — {url}")
    print("=" * 72)
    reponse = await parse_content_url(
        _FakeRequest(),  # type: ignore[arg-type]
        ImportFromUrlRequest(url=url),
        current_user=None,  # type: ignore[arg-type]
    )
    sans_titre = [s for s in reponse.sources if not s.title and s.url]
    print(f"  sources retenues     : {len(reponse.sources)}")
    print(f"  restees sans titre   : {len(sans_titre)}")
    if not sans_titre:
        return

    recuperables = 0
    for source in sans_titre:
        titre = await _titre_de_la_page(source.url)
        etat = f"RECUPERABLE — '{titre[:60]}'" if titre else "la page n'en donne pas"
        if titre:
            recuperables += 1
        print(f"    {source.url[:80]}")
        print(f"      {etat}")

    print()
    print(
        f"  VERDICT : {recuperables}/{len(sans_titre)} recuperables en redemandant "
        f"a la page. {len(sans_titre) - recuperables} n'ont pas de titre a donner."
    )
    print()


async def main() -> None:
    demande = sys.argv[1] if len(sys.argv) > 1 else None
    cibles = {demande: PERSONAS[demande]} if demande in PERSONAS else PERSONAS
    for nom, url in cibles.items():
        await sonder(nom, url)


if __name__ == "__main__":
    asyncio.run(main())
