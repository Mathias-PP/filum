"""Objectif de session : un état qui ne vit pas dans l'historique.

Sur un travail long, l'agent redérive son intention du seul historique. Or
c'est justement le début de l'historique que la compaction ampute : au bout de
quelques compactions il poursuit une version dérivée de sa propre
reformulation, pas la demande de départ.

Ces tests tiennent les trois choses qui font que le dispositif marche : la
persistance hors historique, la réinjection dans le prompt à chaque tour, et le
fait que poser un objectif ne compte pas comme une preuve de travail éditorial.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent_tools.objectif import OUTILS_OBJECTIF, objectif_tools
from app.agent_tools.registry import construire_registre
from app.agent_tools.tool import ToolContext
from app.services import agent as agent_svc
from app.services import agent_sessions


def _outil(nom: str):
    return next(o for o in objectif_tools() if o.name == nom)


class TestCatalogue:
    def test_les_deux_outils_sont_dans_le_registre(self):
        registre = construire_registre()
        assert "definir_objectif" in registre
        assert "avancer_phase" in registre

    def test_aucun_des_deux_n_est_sensible(self):
        """Poser un objectif n'écrit rien de public et se défait en un appel.
        Rendre sensible ce qui est anodin pousse a approuver sans lire."""
        from app.agent_tools.philum import est_sensible

        assert not any(est_sensible(nom, {}) for nom in OUTILS_OBJECTIF)

    def test_ils_ne_comptent_pas_comme_une_ecriture_editoriale(self):
        """`OUTILS_QUI_ECRIVENT` sert a detecter le modele qui annonce une
        action jamais faite. Y compter `definir_objectif` rendrait le controle
        aveugle au cas qu'il vise : annoncer une fiche creee en n'ayant fait que
        poser un objectif."""
        from app.agent_tools.philum import OUTILS_QUI_ECRIVENT

        assert not (OUTILS_OBJECTIF & OUTILS_QUI_ECRIVENT)

    def test_ils_restent_hors_du_parallelisme(self):
        """Ils touchent l'`AsyncSession` du contexte, que ce depot interdit de
        partager entre coroutines."""
        assert OUTILS_OBJECTIF <= agent_svc.OUTILS_NON_PARALLELISABLES

    def test_un_lot_qui_pose_un_objectif_reste_en_file(self):
        appels = [
            ({"id": "a"}, "get_card", {}, True),
            ({"id": "b"}, "definir_objectif", {}, True),
        ]
        assert agent_svc._lot_parallelisable(appels) is False


@pytest.mark.asyncio
class TestPersistance:
    async def test_definir_objectif_ecrit_sur_la_session(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        ctx = ToolContext(
            db=db_session, user=test_user, creator_id=test_user.id, session_id=session.id
        )
        rendu = await _outil("definir_objectif").execute(
            ctx, {"objectif": "Documenter les mitochondries avec cinq sources primaires"}
        )
        assert rendu["objectif"] == "Documenter les mitochondries avec cinq sources primaires"
        relue = await agent_sessions.obtenir(db_session, test_user.id, session.id)
        assert relue.objectif == rendu["objectif"]

    async def test_un_nouvel_objectif_remplace_le_precedent(self, db_session, test_user):
        """Le createur a le droit de changer de cap ; empiler deux objectifs
        contradictoires dans le prompt serait pire que n'en avoir aucun."""
        session = await agent_sessions.creer(db_session, test_user.id)
        ctx = ToolContext(
            db=db_session, user=test_user, creator_id=test_user.id, session_id=session.id
        )
        await _outil("definir_objectif").execute(ctx, {"objectif": "Premier cap"})
        await _outil("definir_objectif").execute(ctx, {"objectif": "Second cap"})
        relue = await agent_sessions.obtenir(db_session, test_user.id, session.id)
        assert relue.objectif == "Second cap"

    async def test_avancer_phase_ne_touche_pas_a_l_objectif(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        ctx = ToolContext(
            db=db_session, user=test_user, creator_id=test_user.id, session_id=session.id
        )
        await _outil("definir_objectif").execute(ctx, {"objectif": "Le cap"})
        rendu = await _outil("avancer_phase").execute(ctx, {"phase": "rédaction des extraits"})
        assert rendu == {"objectif": "Le cap", "phase": "rédaction des extraits"}

    async def test_une_phase_sans_objectif_le_dit(self, db_session, test_user):
        """Sinon la phase flotte : reaffichee a chaque tour, elle laisserait
        croire qu'un objectif existe."""
        session = await agent_sessions.creer(db_session, test_user.id)
        ctx = ToolContext(
            db=db_session, user=test_user, creator_id=test_user.id, session_id=session.id
        )
        rendu = await _outil("avancer_phase").execute(ctx, {"phase": "recherche"})
        assert "definir_objectif" in rendu["avertissement"]

    async def test_l_objectif_est_borne_a_la_colonne(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        ctx = ToolContext(
            db=db_session, user=test_user, creator_id=test_user.id, session_id=session.id
        )
        rendu = await _outil("definir_objectif").execute(ctx, {"objectif": "mot " * 300})
        assert len(rendu["objectif"]) <= agent_sessions.OBJECTIF_MAX

    async def test_un_objectif_vide_est_refuse(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        ctx = ToolContext(
            db=db_session, user=test_user, creator_id=test_user.id, session_id=session.id
        )
        with pytest.raises(ValueError):
            await _outil("definir_objectif").execute(ctx, {"objectif": "   "})

    async def test_hors_conversation_l_outil_le_dit_au_lieu_de_planter(self, db_session, test_user):
        ctx = ToolContext(db=db_session, user=test_user, creator_id=test_user.id)
        rendu = await _outil("definir_objectif").execute(ctx, {"objectif": "un cap"})
        assert "error" in rendu

    async def test_la_session_d_un_autre_createur_est_intouchable(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        autre = SimpleNamespace(id=uuid4())
        ctx = ToolContext(db=db_session, user=autre, creator_id=autre.id, session_id=session.id)
        with pytest.raises(agent_sessions.AgentSessionNotFoundError):
            await _outil("definir_objectif").execute(ctx, {"objectif": "cap volé"})


@pytest.mark.asyncio
class TestInjectionDansLePrompt:
    async def test_l_objectif_pose_revient_dans_le_prompt(self, db_session, test_user):
        session = await agent_sessions.creer(db_session, test_user.id)
        await agent_sessions.fixer_objectif(
            db_session, test_user.id, session.id, objectif="Le cap", phase="recherche"
        )
        bloc = await agent_svc._contexte_objectif(db_session, test_user.id, session.id)
        assert "Le cap" in bloc
        assert "recherche" in bloc

    async def test_sans_objectif_aucune_section_creuse(self, db_session, test_user):
        """Un titre suivi de rien apprend au modele que la section ne veut rien
        dire, et il cesse de la lire quand elle porte enfin quelque chose."""
        session = await agent_sessions.creer(db_session, test_user.id)
        assert await agent_svc._contexte_objectif(db_session, test_user.id, session.id) == ""

    async def test_sans_session_le_prompt_s_assemble_quand_meme(self, db_session, test_user):
        assert await agent_svc._contexte_objectif(db_session, test_user.id, None) == ""

    async def test_une_session_introuvable_ne_casse_pas_le_prompt(self, db_session, test_user):
        """La lecture est du confort : si elle echoue, le tour doit partir."""
        assert await agent_svc._contexte_objectif(db_session, test_user.id, uuid4()) == ""
