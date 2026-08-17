"""Exporte le schema OpenAPI de l'app FastAPI en JSON, sans serveur.

Usage :
    uv run python -m app.scripts.export_openapi

Ecrit toujours au meme endroit (`apps/backend/openapi.json`), en UTF-8. Ce
fichier est la source pour la generation des types TypeScript cote frontend
(`pnpm generate:api` dans apps/frontend).

Ecrire dans stdout marchait sous Linux mais pas sous Windows : la redirection
`>` de PowerShell/cmd utilise cp1252 par defaut, et les caracteres non-ascii
du schema (accents, guillemets francais) sortaient corrompus et illisibles par
le job CI qui relit le fichier en UTF-8.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    # `CI=true` fait generer aux Settings des secrets ephemeres au lieu de lever
    # sur secrets manquants. Sans ce flag, l'export ne peut pas tourner quand un
    # `.env` local force session_secret/master_encryption_key a vide.
    os.environ.setdefault("CI", "true")
    os.environ.setdefault("database_url", "sqlite+aiosqlite:///./export.db")
    os.environ.setdefault("google_client_id", "export.apps.googleusercontent.com")
    os.environ.setdefault("google_client_secret", "export-only")
    os.environ.setdefault("google_redirect_uri", "http://localhost/api/v1/auth/google/callback")

    from app.main import app

    cible = Path(__file__).resolve().parents[2] / "openapi.json"
    with cible.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(app.openapi(), f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"OK : {cible} ({cible.stat().st_size} octets)")


if __name__ == "__main__":
    main()
