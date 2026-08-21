"""Compatibilite des schemas d'outils MCP avec les validateurs stricts."""

from __future__ import annotations

import json

import pytest

from app.mcp_server.schema_compat import aplatir_nullable
from app.mcp_server.server import mcp


class TestAplatirNullable:
    def test_optionnel_simple(self):
        avant = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
        assert aplatir_nullable(avant) == {"type": "string"}

    def test_conserve_les_annotations_voisines(self):
        avant = {
            "anyOf": [{"type": "integer"}, {"type": "null"}],
            "default": None,
            "description": "un nombre",
        }
        assert aplatir_nullable(avant) == {"type": "integer", "description": "un nombre"}

    def test_descend_dans_les_proprietes(self):
        avant = {
            "type": "object",
            "properties": {"a": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
        }
        assert aplatir_nullable(avant)["properties"]["a"] == {"type": "string"}

    def test_laisse_une_vraie_union_tranquille(self):
        """Deux variantes non nulles ne sont pas un optionnel : ne pas y toucher."""
        avant = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
        assert aplatir_nullable(avant) == avant

    def test_ne_mute_pas_l_entree(self):
        avant = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        aplatir_nullable(avant)
        assert "anyOf" in avant


@pytest.mark.asyncio
async def test_aucun_outil_mcp_ne_publie_any_of():
    """Gemini rejette `anyOf` dans une function declaration, et se tait ensuite."""
    outils = await mcp.list_tools()
    assert len(outils) >= 39
    fautifs = [t.name for t in outils if "anyOf" in json.dumps(t.parameters)]
    assert fautifs == []
