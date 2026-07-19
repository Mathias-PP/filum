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
