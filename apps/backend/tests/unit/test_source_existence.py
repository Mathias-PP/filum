"""La garde qui rend impossible la citation d'une source inventee.

Le partage des roles teste ici : ce qui est *prouve* absent est refuse, ce qui
est seulement illisible passe. La seconde moitie compte autant que la premiere,
puisqu'une garde qui refuse des sources reelles finit par etre contournee.
"""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from app.mcp_server.tools_write import add_source, add_sources_batch, create_card
from app.services import source_existence
from app.services.source_existence import (
    SourceInexistanteError,
    verifier_que_la_source_existe,
)


@pytest_asyncio.fixture
async def fiche_brouillon(db_session, test_user):
    return await create_card(
        db_session,
        test_user,
        slug="fiche-existence",
        title="Fiche pour la garde d'existence",
        content_url="https://example.org/video",
    )


def _transport(monkeypatch, code: int) -> None:
    """Fait repondre `code` a toute requete HTTP sortante du module."""

    # La vraie classe, capturee avant le patch : sans cette liaison, le double
    # instancierait `httpx.AsyncClient`, c'est-a-dire lui-meme, a l'infini.
    vraie_classe = httpx.AsyncClient

    class _Fabrique:
        def __init__(self, *args, **kwargs):
            self._c = vraie_classe(transport=httpx.MockTransport(lambda _r: httpx.Response(code)))

        async def __aenter__(self):
            return self._c

        async def __aexit__(self, *exc):
            await self._c.aclose()

    monkeypatch.setattr(source_existence.httpx, "AsyncClient", _Fabrique)
    monkeypatch.setattr(source_existence, "assert_url_is_safe", lambda url: None)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [404, 410])
async def test_une_adresse_qui_repond_absence_est_refusee(monkeypatch, code):
    _transport(monkeypatch, code)
    with pytest.raises(SourceInexistanteError) as capture:
        await verifier_que_la_source_existe("https://exemple.test/article", None)
    assert "memoire" in str(capture.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [200, 401, 403, 429, 500, 503])
async def test_un_mur_ou_une_panne_ne_refuse_rien(monkeypatch, code):
    """Illisible n'est pas inexistant : la garde ne mord que sur l'absence."""
    _transport(monkeypatch, code)
    await verifier_que_la_source_existe("https://exemple.test/article", None)


@pytest.mark.asyncio
async def test_un_doi_inconnu_de_crossref_est_refuse(monkeypatch):
    _transport(monkeypatch, 404)
    with pytest.raises(SourceInexistanteError) as capture:
        await verifier_que_la_source_existe(None, "10.9999/inexistant")
    assert "Crossref" in str(capture.value)


@pytest.mark.asyncio
async def test_un_doi_connu_dispense_de_joindre_l_editeur(monkeypatch):
    """Crossref fait foi : un editeur qui repond 404 decrit sa plomberie."""
    _transport(monkeypatch, 200)
    await verifier_que_la_source_existe("https://editeur.test/x", "10.1000/reel")


@pytest.mark.asyncio
async def test_une_source_sans_adresse_ni_doi_passe(monkeypatch):
    """Un livre imprime n'a pas d'adresse : rien a verifier, rien a refuser."""
    _transport(monkeypatch, 404)
    await verifier_que_la_source_existe("", None)


@pytest.mark.asyncio
async def test_une_panne_reseau_ne_refuse_rien(monkeypatch):
    """Notre propre defaillance ne doit jamais passer pour une preuve d'absence."""

    class _Casse:
        def __init__(self, *args, **kwargs): ...

        async def __aenter__(self):
            raise httpx.ConnectError("reseau coupe")

        async def __aexit__(self, *exc): ...

    monkeypatch.setattr(source_existence.httpx, "AsyncClient", _Casse)
    monkeypatch.setattr(source_existence, "assert_url_is_safe", lambda url: None)
    await verifier_que_la_source_existe("https://exemple.test/article", None)


@pytest.mark.asyncio
async def test_add_source_refuse_une_adresse_introuvable(
    db_session, test_user, fiche_brouillon, monkeypatch
):
    """La garde est bien branchee sur l'outil, pas seulement testable a part."""
    from app.mcp_server import tools_write

    async def _refuser(url, doi):
        raise SourceInexistanteError("Rien a cette adresse.")

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", _refuser)
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError, match="Rien a cette adresse"):
        await add_source(
            db_session,
            test_user,
            card_slug="fiche-existence",
            url="https://invente.test/jamais-publie",
            title="Une source de memoire",
        )


@pytest.mark.asyncio
async def test_le_lot_ecarte_l_introuvable_et_garde_le_reste(
    db_session, test_user, fiche_brouillon, monkeypatch
):
    from app.mcp_server import tools_write

    async def _selon_l_url(url, doi):
        if "invente" in (url or ""):
            raise SourceInexistanteError("Rien a cette adresse.")

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", _selon_l_url)

    lot = await add_sources_batch(
        db_session,
        test_user,
        card_slug="fiche-existence",
        sources=[
            {"url": "https://reel.test/un", "title": "Une source qui existe"},
            {"url": "https://invente.test/deux", "title": "Une source de memoire"},
        ],
    )
    assert len(lot["created"]) == 1
    assert len(lot["failed"]) == 1
    assert lot["failed"][0]["url"] == "https://invente.test/deux"
