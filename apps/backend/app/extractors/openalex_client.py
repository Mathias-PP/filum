"""En-tetes communs a tous les appels OpenAlex.

Depuis le 2026-02-13, OpenAlex exige une cle d'API gratuite : sans elle, les
appels sont reduits a un usage de demonstration, et la resolution des
metadonnees comme celle de l'acces libre s'eteignent. Un seul endroit pour la
cle : un appel qui l'oublierait retomberait sur l'usage sans cle, sans que rien
ne le signale.

La cle part dans l'en-tete ``Authorization``, jamais dans l'URL. Une URL finit
dans les journaux d'acces, dans les messages d'exception de httpx et dans les
traces de debogage ; un en-tete, non.
"""

from __future__ import annotations

from app.core.config import get_settings


def entetes_openalex() -> dict[str, str]:
    cle = get_settings().openalex_api_key.strip()
    return {"Authorization": f"Bearer {cle}"} if cle else {}
