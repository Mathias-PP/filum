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
