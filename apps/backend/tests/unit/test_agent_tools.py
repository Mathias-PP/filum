"""L'agent d'un créateur ne voit jamais le workspace ni les fiches d'un autre.

Le cloisonnement ne tient pas à la sagesse du modèle : il tient au `user` du
`ToolContext`, que la boucle remplit avec l'utilisateur authentifié de la
requête. Ces tests vérifient la garde côté outils, là où un prompt malveillant
viendrait la chercher.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agent_tools.registry import construire_registre, executer
from app.agent_tools.tool import ToolContext
from app.models.user import User


@pytest.fixture
async def autre_user(db_session) -> User:
    user = User(
        id=uuid4(),
        email="autre@example.com",
        username="autrecreateur",
        display_name="Autre Créateur",
        public_key="a" * 64,
        encrypted_private_key="encrypted_autre_key",
        google_id="google_autre_456",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


def _ctx(db, user: User) -> ToolContext:
    return ToolContext(db=db, user=user, creator_id=user.id)


class TestIsolationWorkspace:
    @pytest.mark.asyncio
    async def test_fs_read_ne_voit_pas_le_workspace_dautrui(
        self, db_session, test_user, autre_user
    ):
        registre = construire_registre()
        chemin = "shared/voix-createur.md"
        await executer(
            registre,
            "fs_write",
            {"path": chemin, "content": "Ma voix, mes secrets."},
            _ctx(db_session, test_user),
        )
        await db_session.commit()

        chez_moi = await executer(
            registre, "fs_read", {"path": chemin}, _ctx(db_session, test_user)
        )
        assert chez_moi["found"] is True

        chez_lautre = await executer(
            registre, "fs_read", {"path": chemin}, _ctx(db_session, autre_user)
        )
        assert chez_lautre["found"] is False
        assert chez_lautre["content"] is None

    @pytest.mark.asyncio
    async def test_fs_list_ne_liste_que_le_sien(self, db_session, test_user, autre_user):
        registre = construire_registre()
        await executer(
            registre,
            "fs_write",
            {"path": "runs/ma-fiche/00-brief.md", "content": "brief"},
            _ctx(db_session, test_user),
        )
        await db_session.commit()

        entrees = await executer(
            registre, "fs_list", {"path": "runs/"}, _ctx(db_session, autre_user)
        )
        assert entrees["entries"] == []

    @pytest.mark.asyncio
    async def test_fs_write_nempiete_pas_sur_lautre(self, db_session, test_user, autre_user):
        registre = construire_registre()
        chemin = "shared/garde-fous.md"
        await executer(
            registre, "fs_write", {"path": chemin, "content": "à moi"}, _ctx(db_session, test_user)
        )
        await executer(
            registre,
            "fs_write",
            {"path": chemin, "content": "à lui"},
            _ctx(db_session, autre_user),
        )
        await db_session.commit()

        mien = await executer(registre, "fs_read", {"path": chemin}, _ctx(db_session, test_user))
        assert mien["content"] == "à moi"


class TestIsolationFiches:
    @pytest.mark.asyncio
    async def test_update_card_dautrui_refuse(self, db_session, test_user, autre_user):
        registre = construire_registre()
        cree = await executer(
            registre,
            "create_card",
            {"slug": "fiche-privee", "title": "Ma fiche"},
            _ctx(db_session, test_user),
        )
        assert "error" not in cree
        await db_session.commit()

        vole = await executer(
            registre,
            "update_card",
            {"slug": "fiche-privee", "title": "Détournée"},
            _ctx(db_session, autre_user),
        )
        assert "error" in vole

        intacte = await executer(
            registre,
            "update_card",
            {"slug": "fiche-privee", "description": "toujours à moi"},
            _ctx(db_session, test_user),
        )
        assert intacte["title"] == "Ma fiche"
