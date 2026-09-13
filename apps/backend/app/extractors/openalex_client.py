"""Parametres communs a tous les appels OpenAlex.

Depuis le 2026-02-13, OpenAlex exige une cle d'API gratuite : sans elle, le
budget tombe a 100 credits par jour, et la resolution des metadonnees comme
celle de l'acces libre s'eteignent en quelques dizaines d'appels. Un seul
endroit pour la cle : un appel qui l'oublierait retomberait sur le budget sans
cle, sans que rien ne le signale.
"""

from __future__ import annotations

from app.core.config import get_settings


def parametres_openalex() -> dict[str, str]:
    cle = get_settings().openalex_api_key.strip()
    return {"api_key": cle} if cle else {}
