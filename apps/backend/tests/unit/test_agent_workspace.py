from __future__ import annotations

import pytest

from app.services import agent_workspace
from app.services.agent_workspace import WorkspaceError


@pytest.mark.asyncio
async def test_normaliser_chemin_accepte_relatifs():
    assert (
        agent_workspace.normaliser_chemin("shared/principes-editoriaux.md")
        == "shared/principes-editoriaux.md"
    )
    assert agent_workspace.normaliser_chemin("AGENTS.md") == "AGENTS.md"
    assert agent_workspace.normaliser_chemin("CONTEXT.md") == "CONTEXT.md"
    assert (
        agent_workspace.normaliser_chemin("stages/01-brief/CONTEXT.md")
        == "stages/01-brief/CONTEXT.md"
    )
    assert agent_workspace.normaliser_chemin("agents/mon-agent.yaml") == "agents/mon-agent.yaml"
    assert (
        agent_workspace.normaliser_chemin("runs/mon-slug/00-brief.md")
        == "runs/mon-slug/00-brief.md"
    )


@pytest.mark.asyncio
async def test_normaliser_chemin_backslashes_windows():
    assert (
        agent_workspace.normaliser_chemin("stages\\01-brief\\CONTEXT.md")
        == "stages/01-brief/CONTEXT.md"
    )


@pytest.mark.asyncio
async def test_normaliser_chemin_nettoie_points_et_slashes():
    assert agent_workspace.normaliser_chemin("./shared//garde-fous.md") == "shared/garde-fous.md"


@pytest.mark.asyncio
async def test_normaliser_chemin_refuse_remontee_hors_racine():
    for chemin in ("../AGENTS.md", "shared/../../etc/passwd", "..", "shared/.."):
        with pytest.raises(WorkspaceError):
            agent_workspace.normaliser_chemin(chemin)


@pytest.mark.asyncio
async def test_normaliser_chemin_refuse_absolus():
    for chemin in (
        "/etc/passwd",
        "C:\\Windows\\system32",
        "file:///etc/passwd",
        "https://evil.com/x",
    ):
        with pytest.raises(WorkspaceError):
            agent_workspace.normaliser_chemin(chemin)


@pytest.mark.asyncio
async def test_normaliser_chemin_refuse_racine_inconnue():
    for chemin in ("biblio/x.md", "nimporte/fichier.md", "tmp/seed"):
        with pytest.raises(WorkspaceError):
            agent_workspace.normaliser_chemin(chemin)


@pytest.mark.asyncio
async def test_sha256_stable():
    assert agent_workspace.calculer_sha256("bonjour") == agent_workspace.calculer_sha256("bonjour")
    assert agent_workspace.calculer_sha256("bonjour") != agent_workspace.calculer_sha256("bonjour ")


@pytest.mark.asyncio
async def test_ecrire_lire_supprimer(db_session, test_user):
    fichier = await agent_workspace.ecrire(
        db_session, test_user.id, "runs/mon-slug/00-brief.md", "contenu"
    )
    assert fichier.sha256 == agent_workspace.calculer_sha256("contenu")
    await db_session.commit()

    lu = await agent_workspace.lire(db_session, test_user.id, "runs/mon-slug/00-brief.md")
    assert lu is not None
    assert lu.content == "contenu"

    await agent_workspace.supprimer(db_session, test_user.id, "runs/mon-slug/00-brief.md")
    await db_session.commit()
    assert await agent_workspace.lire(db_session, test_user.id, "runs/mon-slug/00-brief.md") is None


@pytest.mark.asyncio
async def test_ecrire_upsert_recalcule_sha(db_session, test_user):
    await agent_workspace.ecrire(db_session, test_user.id, "shared/note.md", "v1")
    await db_session.commit()
    fichier = await agent_workspace.ecrire(db_session, test_user.id, "shared/note.md", "v2")
    await db_session.commit()

    assert fichier.sha256 == agent_workspace.calculer_sha256("v2")
    assert await agent_workspace.lire(db_session, test_user.id, "shared/note.md") is not None


@pytest.mark.asyncio
async def test_lister_arborescence(db_session, test_user):
    await agent_workspace.ecrire(db_session, test_user.id, "stages/01-brief/CONTEXT.md", "a")
    await agent_workspace.ecrire(
        db_session, test_user.id, "stages/02-sources-collectees/CONTEXT.md", "b"
    )
    await agent_workspace.ecrire(db_session, test_user.id, "shared/voix-createur.md", "c")
    await db_session.commit()

    arbre = await agent_workspace.lister(db_session, test_user.id)
    chemins = {e["path"] for e in arbre}
    assert "stages/01-brief/CONTEXT.md" in chemins
    assert "stages/01-brief" in chemins
    assert "stages" in chemins
    assert "shared/voix-createur.md" in chemins

    sous = await agent_workspace.lister(db_session, test_user.id, "stages/")
    assert {e["path"] for e in sous} == {
        "stages",
        "stages/01-brief",
        "stages/02-sources-collectees",
        "stages/01-brief/CONTEXT.md",
        "stages/02-sources-collectees/CONTEXT.md",
    }


@pytest.mark.asyncio
async def test_seed_cree_tous_les_fichiers_template(db_session, test_user):
    count = await agent_workspace.seed(db_session, test_user.id)
    await db_session.commit()
    assert count > 0

    arbre = await agent_workspace.lister(db_session, test_user.id)
    chemins = {e["path"] for e in arbre if e["type"] == "file"}
    assert "AGENTS.md" in chemins
    assert "CONTEXT.md" in chemins
    assert "shared/principes-editoriaux.md" in chemins
    assert "stages/07-publication/CONTEXT.md" in chemins
    assert "_core/templates/brief.md" in chemins


@pytest.mark.asyncio
async def test_seed_idempotent_preserve_les_modifs(db_session, test_user):
    await agent_workspace.seed(db_session, test_user.id)
    await db_session.commit()

    await agent_workspace.ecrire(
        db_session, test_user.id, "shared/principes-editoriaux.md", "MODIFIÉ PAR LE CRÉATEUR"
    )
    await db_session.commit()

    count = await agent_workspace.seed(db_session, test_user.id)
    await db_session.commit()
    assert count == 0

    lu = await agent_workspace.lire(db_session, test_user.id, "shared/principes-editoriaux.md")
    assert lu.content == "MODIFIÉ PAR LE CRÉATEUR"


@pytest.mark.asyncio
async def test_ecrire_chemin_invalide_leve_erreur(db_session, test_user):
    with pytest.raises(WorkspaceError):
        await agent_workspace.ecrire(db_session, test_user.id, "../../etc/passwd", "x")
    with pytest.raises(WorkspaceError):
        await agent_workspace.ecrire(db_session, test_user.id, "hors/racine.md", "x")
