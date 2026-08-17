"""Le contrat OpenAPI committe doit refleter le code FastAPI courant.

Le fichier `apps/backend/openapi.json` est la source de verite consommee par le
frontend (`pnpm run generate:api` produit `src/lib/api/generated.ts`). Un
endpoint change dans le code sans regeneration du fichier ne casse rien tant
que personne ne s'en sert -- puis le premier appel touche une signature
inexistante et l'erreur remonte en prod. Ce test bloque l'oubli au commit.

Si ce test echoue :

    cd apps/backend
    uv run python -m app.scripts.export_openapi > openapi.json
    cd ../frontend
    pnpm run generate:api

puis commit `openapi.json` et `generated.ts` ensemble.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_openapi_committe_reflete_l_app_courante():
    from app.main import app

    fichier = Path(__file__).resolve().parents[2] / "openapi.json"
    assert fichier.exists(), (
        "openapi.json manquant. Regenerer avec "
        "`uv run python -m app.scripts.export_openapi > openapi.json`."
    )

    committe = json.loads(fichier.read_text(encoding="utf-8"))
    courant = app.openapi()

    if committe != courant:
        chemins_committe = set(committe.get("paths", {}).keys())
        chemins_courants = set(courant.get("paths", {}).keys())
        ajouts = chemins_courants - chemins_committe
        suppressions = chemins_committe - chemins_courants
        details = []
        if ajouts:
            details.append(f"routes ajoutees au code, absentes du fichier : {sorted(ajouts)}")
        if suppressions:
            details.append(f"routes du fichier absentes du code : {sorted(suppressions)}")
        if not details:
            details.append("meme routes mais signatures ou schemas divergent")
        raise AssertionError(
            "openapi.json ne reflete plus le code. "
            + " ; ".join(details)
            + ". Regenerer avec `uv run python -m app.scripts.export_openapi > openapi.json` "
            "puis `pnpm run generate:api` cote frontend."
        )
