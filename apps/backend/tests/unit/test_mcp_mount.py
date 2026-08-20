from __future__ import annotations


def test_mcp_route_is_mounted():
    from app.main import app

    mounted = [r.path for r in app.routes if getattr(r, "path", "").startswith("/mcp")]
    assert mounted, "Le serveur MCP doit etre monte sur /mcp"


def test_mcp_tools_registered():
    import asyncio

    from app.mcp_server.server import mcp

    # FastMCP 3.x: list_tools() returns a list of Tool objects with a .name attribute
    loop = asyncio.new_event_loop()
    try:
        tools_list = loop.run_until_complete(mcp.list_tools())
    finally:
        loop.close()

    names = {t.name for t in tools_list}
    assert {"search_cards", "get_card", "get_source", "find_cards_citing"} <= names


def test_mcp_rate_limit_triggers_429():
    from fastapi.testclient import TestClient

    from app.main import _mcp_rate_storage, app

    _mcp_rate_storage.reset()
    client = TestClient(app)

    # /mcp emits a 307 to /mcp/ (no auth needed to observe). Under the limit
    # we consistently get 307; past it we get our 429.
    for _ in range(60):
        r = client.get("/mcp", follow_redirects=False)
        assert r.status_code != 429, f"unexpected 429 at request {_}"

    over = client.get("/mcp", follow_redirects=False)
    assert over.status_code == 429
    body = over.json()
    assert body["error"]["code"] == "rate_limit_exceeded"
    assert over.headers.get("Retry-After") == "60"


def _client():
    from fastapi.testclient import TestClient

    from app.main import _mcp_rate_storage, app

    _mcp_rate_storage.reset()
    return TestClient(app)


def _token_valide(user_id="00000000-0000-0000-0000-000000000001"):
    from datetime import UTC, datetime, timedelta

    import jwt

    from app.core.config import get_settings
    from app.services.auth import ALGORITHM

    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "aud": "mcp",
        },
        get_settings().session_secret,
        algorithm=ALGORITHM,
    )


def test_porte_compte_repond_401_sans_token():
    """Sans 401, aucun client MCP ne declenche la decouverte OAuth : c'est ce
    401 qui rend la connexion en un clic possible."""
    r = _client().get("/mcp-account/", follow_redirects=False)
    assert r.status_code == 401
    entete = r.headers.get("WWW-Authenticate", "")
    assert "resource_metadata=" in entete
    assert "/.well-known/oauth-protected-resource/mcp-account" in entete


def test_porte_publique_reste_ouverte_sans_token():
    """Un agent anonyme (LLM local, client sans compte) doit pouvoir lire."""
    r = _client().get("/mcp", follow_redirects=False)
    assert r.status_code != 401


def test_un_token_invalide_vaut_401_meme_sur_la_porte_publique():
    """Retomber silencieusement en anonyme ferait croire l'utilisateur
    connecte alors que toutes ses ecritures echoueraient."""
    r = _client().get(
        "/mcp", headers={"Authorization": "Bearer pas-un-jwt"}, follow_redirects=False
    )
    assert r.status_code == 401
    assert "/.well-known/oauth-protected-resource/mcp" in r.headers.get("WWW-Authenticate", "")


def test_un_token_valide_passe_la_porte_compte():
    # `with` : la requete atteint reellement l'app MCP, qui exige son lifespan.
    with _client() as client:
        r = client.get(
            "/mcp-account/",
            headers={"Authorization": f"Bearer {_token_valide()}"},
            follow_redirects=False,
        )
    assert r.status_code != 401


def test_les_deux_documents_well_known_annoncent_leur_propre_ressource():
    client = _client()
    compte = client.get("/.well-known/oauth-protected-resource/mcp-account").json()
    public = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert compte["resource"].endswith("/mcp-account/")
    assert public["resource"].endswith("/mcp/")


def test_mcp_rate_limit_ignores_other_paths():
    from fastapi.testclient import TestClient

    from app.main import _mcp_rate_storage, app

    _mcp_rate_storage.reset()
    client = TestClient(app)

    # Exhaust the /mcp bucket, then check /health still responds normally.
    for _ in range(61):
        client.get("/mcp", follow_redirects=False)

    r = client.get("/health")
    assert r.status_code == 200
