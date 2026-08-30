"""La cle de recherche web part la ou chaque fournisseur l'attend.

Un envoi au mauvais endroit ne casse rien de visible en test : la fonction rend
une liste vide, exactement comme une recherche sans resultat. C'est en
production que ca se voit, en 401, et seulement le jour ou quelqu'un configure
le fournisseur. D'ou ce test, qui inspecte la requete sortante plutot que sa
reponse.
"""

from __future__ import annotations

import httpx
import pytest

from app.agent_tools import web

_VRAI_CLIENT = httpx.AsyncClient

# Par fournisseur : l'en-tete qui doit porter la cle, sa valeur attendue, et la
# reponse minimale qui donne un resultat exploitable.
_FOURNISSEURS = {
    "tavily": (
        "Authorization",
        "Bearer une-cle",
        {"results": [{"url": "https://a.test", "title": "Un titre", "content": "Un extrait."}]},
    ),
    "serper": (
        "X-API-KEY",
        "une-cle",
        {"organic": [{"link": "https://a.test", "title": "Un titre", "snippet": "Un extrait."}]},
    ),
    "brave": (
        "X-Subscription-Token",
        "une-cle",
        {
            "web": {
                "results": [
                    {"url": "https://a.test", "title": "Un titre", "description": "Un extrait."}
                ]
            }
        },
    ),
    "exa": (
        "x-api-key",
        "une-cle",
        {"results": [{"url": "https://a.test", "title": "Un titre", "text": "Un extrait."}]},
    ),
}


@pytest.fixture
def requetes(monkeypatch):
    """Intercepte la requete sortante et rend la reponse du fournisseur voulu."""
    vues: list[httpx.Request] = []
    charge: dict[str, object] = {}

    def fabrique(**kwargs):
        async def repondre(request: httpx.Request) -> httpx.Response:
            await request.aread()
            vues.append(request)
            return httpx.Response(200, json=charge["corps"])

        kwargs.pop("transport", None)
        return _VRAI_CLIENT(transport=httpx.MockTransport(repondre), **kwargs)

    monkeypatch.setattr(web.httpx, "AsyncClient", fabrique)
    return vues, charge


@pytest.mark.asyncio
@pytest.mark.parametrize("fournisseur", sorted(_FOURNISSEURS))
async def test_la_cle_part_dans_l_entete_jamais_dans_le_corps(fournisseur, requetes):
    vues, charge = requetes
    entete, attendu, charge["corps"] = _FOURNISSEURS[fournisseur]

    resultats = await web._rechercher_brut(fournisseur, "une-cle", "une requete")

    assert len(vues) == 1
    requete = vues[0]
    assert requete.headers.get(entete) == attendu
    # Le corps ne doit jamais la porter : il finit dans les journaux d'acces des
    # intermediaires, l'en-tete non.
    assert b"une-cle" not in requete.content
    assert resultats == [{"url": "https://a.test", "title": "Un titre", "snippet": "Un extrait."}]


@pytest.mark.asyncio
async def test_un_fournisseur_inconnu_se_signale(requetes):
    with pytest.raises(ValueError, match="inconnu"):
        await web._rechercher_brut("un-inconnu", "une-cle", "une requete")
