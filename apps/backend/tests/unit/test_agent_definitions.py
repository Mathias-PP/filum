from __future__ import annotations

import pytest

from app.agent_tools.registry import noms_outils_connus
from app.services import agent_definitions, agent_workspace
from app.services.agent_definitions import DefinitionInvalideError, parser

CONNUS = noms_outils_connus()

VALIDE = """
slug: mon-agent
name: Mon agent
contract: "Fait une chose et la fait bien."
layer: L2
tools:
  - get_card
  - list_sources
context:
  - shared/garde-fous.md
system_prompt: |
  Tu fais une chose.
"""


def test_parser_accepte_une_definition_complete():
    d = parser("agents/mon-agent.yaml", VALIDE, noms_connus=CONNUS)
    assert d.slug == "mon-agent"
    assert d.name == "Mon agent"
    assert d.tools == ("get_card", "list_sources")
    assert d.context == ("shared/garde-fous.md",)
    assert d.layer == "L2"
    assert d.model_hint is None
    assert d.system_prompt == "Tu fais une chose."


def test_parser_dedoublonne_outils_et_contexte():
    contenu = VALIDE.replace("  - list_sources\n", "  - list_sources\n  - get_card\n").replace(
        "  - shared/garde-fous.md\n", "  - shared/garde-fous.md\n  - ./shared/garde-fous.md\n"
    )
    d = parser("agents/mon-agent.yaml", contenu, noms_connus=CONNUS)
    assert d.tools == ("get_card", "list_sources")
    assert d.context == ("shared/garde-fous.md",)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            lambda s: s.replace("  - get_card\n", "  - outil_qui_nexiste_pas\n"), id="outil-inconnu"
        ),
        pytest.param(
            lambda s: s.replace("  - get_card\n  - list_sources\n", "  []\n"), id="tools-vide"
        ),
        pytest.param(
            lambda s: s.replace("slug: mon-agent", "slug: Mon_Agent"), id="slug-non-kebab"
        ),
        pytest.param(lambda s: s.replace("layer: L2", "layer: L9"), id="layer-inconnu"),
        pytest.param(lambda s: s.replace("name: Mon agent\n", ""), id="name-absent"),
        pytest.param(
            lambda s: s.replace('contract: "Fait une chose et la fait bien."\n', ""),
            id="contract-absent",
        ),
        pytest.param(
            lambda s: s.replace("  - shared/garde-fous.md", "  - ../../etc/passwd"),
            id="contexte-hors-workspace",
        ),
        pytest.param(lambda s: "slug: [oups\n  - non", id="yaml-illisible"),
        pytest.param(lambda s: "juste du texte", id="pas-un-dictionnaire"),
    ],
)
def test_parser_rejette(mutation):
    with pytest.raises(DefinitionInvalideError):
        parser("agents/mon-agent.yaml", mutation(VALIDE), noms_connus=CONNUS)


def test_parser_exige_que_le_slug_corresponde_au_fichier():
    with pytest.raises(DefinitionInvalideError):
        parser("agents/autre-nom.yaml", VALIDE, noms_connus=CONNUS)


def test_parser_accepte_les_agents_livres():
    """Les definitions du seed doivent charger : elles sont servies telles quelles."""
    dossier = agent_workspace.SEED_DIR / "agents"
    fichiers = sorted(dossier.glob("*.yaml"))
    assert fichiers, "aucun agent dans le snapshot du seed"
    for fichier in fichiers:
        chemin = f"agents/{fichier.name}"
        d = parser(chemin, fichier.read_text(encoding="utf-8"), noms_connus=CONNUS)
        assert d.slug == fichier.stem
    assert agent_definitions.SLUG_DEFAUT in {f.stem for f in fichiers}


@pytest.mark.asyncio
async def test_lister_marque_les_agents_livres_et_signale_les_rejets(db_session, test_user):
    await agent_workspace.seed(db_session, test_user.id)
    await agent_workspace.ecrire(
        db_session, test_user.id, "agents/perso.yaml", VALIDE.replace("mon-agent", "perso")
    )
    await agent_workspace.ecrire(
        db_session, test_user.id, "agents/casse.yaml", "slug: casse\nname: X\n"
    )
    await db_session.commit()

    valides, rejetes = await agent_definitions.lister(db_session, test_user.id)
    par_slug = {d.slug: d for d in valides}
    assert par_slug[agent_definitions.SLUG_DEFAUT].builtin is True
    assert par_slug["perso"].builtin is False
    # L'assistant generaliste ouvre la liste : c'est le choix par defaut.
    assert valides[0].slug == agent_definitions.SLUG_DEFAUT
    assert [r.path for r in rejetes] == ["agents/casse.yaml"]
    assert rejetes[0].raison


@pytest.mark.asyncio
async def test_lister_ignore_les_fichiers_non_yaml(db_session, test_user):
    await agent_workspace.ecrire(db_session, test_user.id, "agents/CONTEXT.md", "# Doc")
    await agent_workspace.ecrire(
        db_session, test_user.id, "agents/perso.yaml", VALIDE.replace("mon-agent", "perso")
    )
    await db_session.commit()

    valides, rejetes = await agent_definitions.lister(db_session, test_user.id)
    assert [d.slug for d in valides] == ["perso"]
    assert rejetes == []


@pytest.mark.asyncio
async def test_obtenir_rend_none_sur_slug_absent(db_session, test_user):
    await agent_workspace.seed(db_session, test_user.id)
    await db_session.commit()

    assert await agent_definitions.obtenir(db_session, test_user.id, "fantome") is None
    assert await agent_definitions.obtenir(db_session, test_user.id, "") is None
    trouve = await agent_definitions.obtenir(
        db_session, test_user.id, agent_definitions.SLUG_DEFAUT
    )
    assert trouve is not None and trouve.tools


def test_chemin_de():
    assert agent_definitions.chemin_de("relecteur") == "agents/relecteur.yaml"
