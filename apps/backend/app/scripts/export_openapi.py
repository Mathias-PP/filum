"""Exporte le schema OpenAPI de l'app FastAPI en JSON, sans serveur.

Usage :
    uv run python -m app.scripts.export_openapi > openapi.json

Sert de source pour la generation des types TypeScript cote frontend
(`pnpm generate:api` dans apps/frontend). Les env vars obligatoires de
Settings recoivent des valeurs factices : seul le schema est construit,
aucune connexion DB ni appel externe.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    os.environ.setdefault("database_url", "sqlite+aiosqlite:///./export.db")
    os.environ.setdefault("session_secret", "export-only-secret-32-characters!!")
    os.environ.setdefault("master_encryption_key", "export-only-key-32-characters!!!")
    os.environ.setdefault("google_client_id", "export.apps.googleusercontent.com")
    os.environ.setdefault("google_client_secret", "export-only")
    os.environ.setdefault("google_redirect_uri", "http://localhost/api/v1/auth/google/callback")

    from app.main import app

    json.dump(app.openapi(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
