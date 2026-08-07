"""Audit du pipeline d'extraction sur un contenu reel par persona.

Les fiches de test du corpus actuel sont un echantillon de un, ecrit par la
meme personne, sur le meme genre de contenu. Elles ne disent rien de ce que
recevrait un journaliste, un vulgarisateur, un essayiste ou une institution.

Ce script prend une URL reelle par persona et fait tourner
`parse_content_url`, c'est-a-dire exactement le code que declenche le bouton
« importer depuis une URL » du tableau de bord. Il n'ecrit rien : ni en base,
ni en prod. Il repond a une seule question par persona : qu'est-ce que cette
personne verrait a l'ecran, et est-ce utilisable ?

Usage : uv run python scripts/audit_personas.py [persona]
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("database_url", "sqlite+aiosqlite:///./audit_personas.db")
os.environ.setdefault("session_secret", "audit-secret-for-local-run-32chars")
os.environ.setdefault("master_encryption_key", "audit-key-for-local-run-32bytes")
os.environ.setdefault("google_client_id", "audit.apps.googleusercontent.com")
os.environ.setdefault("google_client_secret", "audit-secret")
os.environ.setdefault("google_redirect_uri", "http://localhost/api/v1/auth/google/callback")
os.environ.setdefault("ci", "true")

from app.core.config import Settings, get_settings  # noqa: E402

Settings.model_config["case_sensitive"] = False
get_settings.cache_clear()

from app.api.v1.endpoints.imports import (  # noqa: E402
    ImportFromUrlRequest,
    parse_content_url,
)

# Une URL publique reelle par persona, choisie pour etre representative du
# genre et non pour bien se comporter.
PERSONAS: dict[str, tuple[str, str]] = {
    "journaliste": (
        "Article de presse d'investigation",
        "https://www.propublica.org/article/how-the-irs-was-gutted",
    ),
    "vulgarisateur": (
        "Video YouTube de vulgarisation",
        "https://www.youtube.com/watch?v=aircAruvnKk",
    ),
    "essayiste": (
        "Essai de blog long format",
        "https://gwern.net/scaling-hypothesis",
    ),
    "institution": (
        "Rapport institutionnel",
        "https://www.who.int/news-room/fact-sheets/detail/depression",
    ),
}


class _FakeRequest:
    """`parse_content_url` ne lit la requete que pour le rate-limit, retire."""

    client = None
    headers: dict[str, str] = {}


async def run(persona: str, label: str, url: str) -> None:
    print(f"\n{'=' * 72}\n{persona.upper()} — {label}\n{url}\n{'=' * 72}")
    try:
        res = await parse_content_url(
            _FakeRequest(),  # type: ignore[arg-type]
            ImportFromUrlRequest(url=url),
            current_user=None,  # type: ignore[arg-type]
        )
    except Exception as exc:  # noqa: BLE001 - on veut le verdict, pas le crash
        print(f"  ECHEC {type(exc).__name__}: {exc}")
        return

    print(f"  fetch                : {res.fetch_status}")
    print(f"  titre                : {res.card.title!r}")
    print(f"  auteurs du contenu   : {res.card.authors!r}")
    print(f"  section References   : {res.references_section_found}")
    print(f"  confiance            : {res.extraction_confidence}")
    print(f"  sources retenues     : {len(res.sources)}")
    print(
        f"    dont oracle={res.refs_from_oracle} enrichissement={res.refs_from_enrichment}"
        f"  | droppees: validation={res.refs_dropped_validation}"
        f" scoring={res.refs_dropped_scoring} halluc={res.refs_dropped_s2_hallucination}"
    )

    sans_titre = sum(1 for s in res.sources if not (s.title or "").strip())
    sans_url = sum(1 for s in res.sources if not (s.url or "").strip())
    sans_annee = sum(1 for s in res.sources if not s.published_at)
    print(
        f"  qualite              : sans titre={sans_titre} sans url={sans_url} sans annee={sans_annee}"
    )

    for s in res.sources[:5]:
        titre = (s.title or "(sans titre)")[:70]
        print(f"    - {titre}  [{s.category}]")
    if len(res.sources) > 5:
        print(f"    … et {len(res.sources) - 5} autres")


async def main() -> None:
    wanted = sys.argv[1:] or list(PERSONAS)
    for persona in wanted:
        if persona not in PERSONAS:
            print(f"persona inconnu : {persona}")
            continue
        label, url = PERSONAS[persona]
        await run(persona, label, url)


if __name__ == "__main__":
    asyncio.run(main())
