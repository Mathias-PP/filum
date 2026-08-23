"""Tests du catalogue d'outils Philum : complétude, descriptions, schémas enum."""

from __future__ import annotations

from app.agent_tools.philum import _ECRITURE, _LECTURE, _description, _json_schema, philum_tools
from app.mcp_server import tools_write as ecriture
from app.models.source import AuthorKind, SourceCategory, SourceStance
from app.schemas.biblio_card import ContentType, Platform, Visibility


class TestCatalogueCompletude:
    def test_catalogue_contient_delete_excerpt(self):
        assert "delete_excerpt" in _ECRITURE

    def test_catalogue_correspond_aux_fonctions_exportees(self):
        """Chaque nom du tuple existe bien dans tools_write."""
        for nom in _ECRITURE:
            assert hasattr(ecriture, nom), f"Fonction manquante dans tools_write : {nom!r}"

    def test_lecture_correspond_aux_fonctions_exportees(self):
        from app.mcp_server import tools as lecture

        for nom in _LECTURE:
            assert hasattr(lecture, nom), f"Fonction manquante dans tools : {nom!r}"

    def test_philum_tools_inclut_delete_excerpt(self):
        outils = {t.name for t in philum_tools()}
        assert "delete_excerpt" in outils


class TestDescriptions:
    def test_description_non_tronquee(self):
        """Un docstring multi-lignes doit etre entierement transmis au modele."""

        def fn_multi():
            """Premiere ligne.

            Deuxieme phrase qui documente des details importants.
            """

        desc = _description(fn_multi)
        assert "Deuxieme phrase" in desc

    def test_description_aplatie_sans_saut_de_ligne(self):
        """La description ne contient aucun saut de ligne."""

        def fn_multi():
            """Ligne A.

            Ligne B.
            """

        desc = _description(fn_multi)
        assert "\n" not in desc

    def test_description_fallback_sur_nom(self):
        def fn_sans_doc():
            pass

        fn_sans_doc.__doc__ = None
        desc = _description(fn_sans_doc)
        assert desc == "fn_sans_doc"

    def test_aucun_outil_ne_se_presente_par_son_seul_nom(self):
        """Un outil sans docstring retombe sur `__name__` et devient muet.

        `search_cards`, `get_card`, `get_source` et `find_cards_citing` ont vecu
        ainsi : le modele voyait `"description": "get_card"` et ne pouvait pas
        deviner que cet outil lit une fiche. En conversation reelle il repondait
        « je n'ai pas acces a la fiche » alors que l'outil etait dans son
        catalogue. Le repli sur le nom reste un filet utile, mais aucun outil
        livre ne doit s'en contenter.
        """
        muets = [t.name for t in philum_tools() if t.description.strip() == t.name]
        assert muets == [], f"outils sans description : {muets}"

    def test_toute_description_livree_est_substantielle(self):
        """Une description doit dire ce que fait l'outil et ce qu'il rend."""
        courtes = [(t.name, t.description) for t in philum_tools() if len(t.description) < 60]
        assert courtes == [], f"descriptions trop courtes : {courtes}"

    def test_get_my_card_dans_le_catalogue(self):
        """Lire sa propre fiche, brouillon compris, doit etre outille.

        `get_card` filtre sur publie ET public : sans `get_my_card`, aucun outil
        ne rendait la description ni le transcript d'un brouillon, et l'agent
        concluait sincerement qu'il n'y avait pas acces.
        """
        outils = {t.name: t for t in philum_tools()}
        assert "get_my_card" in outils
        assert "brouillon" in outils["get_my_card"].description

    def test_get_card_annonce_qu_il_ignore_les_brouillons(self):
        """La distinction corpus public / fiches du createur vit dans le schema.

        C'est elle qui evite que le modele appelle `get_card` sur un brouillon,
        recoive `null` et en deduise que la fiche n'existe pas.
        """
        outils = {t.name: t for t in philum_tools()}
        assert "get_my_card" in outils["get_card"].description
        assert "get_my_card" in outils["search_cards"].description

    def test_create_card_description_contient_publication(self):
        """create_card doit mentionner que la publication est distincte."""
        from app.mcp_server.tools_write import create_card

        desc = _description(create_card)
        assert "publish" in desc.lower() or "publication" in desc.lower()


class TestSchemaJson:
    def test_schema_liste_de_dicts(self):
        from typing import Any

        schema = _json_schema(list[dict[str, Any]])
        assert schema == {"type": "array", "items": {"type": "object"}}

    def test_schema_dict_simple(self):
        schema = _json_schema(dict)
        assert schema == {"type": "object"}

    def test_schema_str(self):
        assert _json_schema(str) == {"type": "string"}

    def test_schema_int(self):
        assert _json_schema(int) == {"type": "integer"}

    def test_schema_bool(self):
        assert _json_schema(bool) == {"type": "boolean"}

    def test_schema_liste_de_str(self):
        assert _json_schema(list[str]) == {"type": "array", "items": {"type": "string"}}


class TestEnumsDansSchemas:
    def _schema_outil(self, nom: str) -> dict:
        outils = {t.name: t for t in philum_tools()}
        return outils[nom].parameters

    def test_enums_du_schema_alignes_sur_les_modeles(self):
        """Le schema de create_card porte exactement les valeurs de Platform."""
        schema = self._schema_outil("create_card")
        attendus = [e.value for e in Platform]
        assert schema["properties"]["platform"]["enum"] == attendus

    def test_content_type_dans_schema_create_card(self):
        schema = self._schema_outil("create_card")
        attendus = [e.value for e in ContentType]
        assert schema["properties"]["content_type"]["enum"] == attendus

    def test_visibility_dans_schema_create_card(self):
        schema = self._schema_outil("create_card")
        attendus = [e.value for e in Visibility]
        assert schema["properties"]["visibility"]["enum"] == attendus

    def test_category_dans_schema_add_source(self):
        schema = self._schema_outil("add_source")
        attendus = [e.value for e in SourceCategory]
        assert schema["properties"]["category"]["enum"] == attendus

    def test_author_kind_dans_schema_add_source(self):
        schema = self._schema_outil("add_source")
        attendus = [e.value for e in AuthorKind]
        assert schema["properties"]["author_kind"]["enum"] == attendus

    def test_stance_dans_schema_add_source(self):
        schema = self._schema_outil("add_source")
        attendus = [e.value for e in SourceStance]
        assert schema["properties"]["stance"]["enum"] == attendus

    def test_add_sources_batch_items_type_object(self):
        """add_sources_batch(sources: list[dict]) doit rendre items.type == object."""
        schema = self._schema_outil("add_sources_batch")
        sources_prop = schema["properties"]["sources"]
        assert sources_prop["type"] == "array"
        assert sources_prop["items"]["type"] == "object"

    def test_aucun_enum_sur_champ_non_liste(self):
        """Un champ qui n'est pas dans _ENUMS_PAR_PARAMETRE ne recoit pas enum."""
        schema = self._schema_outil("create_card")
        assert "enum" not in schema["properties"]["slug"]
        assert "enum" not in schema["properties"]["title"]
