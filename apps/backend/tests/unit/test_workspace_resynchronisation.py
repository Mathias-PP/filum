"""Propager les évolutions du template sans écraser le travail de la personne.

`seed()` n'insère que les chemins absents, ce qui protège les éditions mais
fige le workspace à sa date de création. Mesure du 2026-08-30 sur un workspace
réel en production : 10 fichiers à jour sur 27, 9 dans une version ancienne, et
le répertoire `agents/` entier jamais arrivé. L'agent travaillait donc avec une
documentation d'outils périmée.

Le contenu seul ne dit pas quoi faire d'un fichier qui diffère du template :
édité ici, ou template qui a avancé ? Les deux appellent l'inverse l'un de
l'autre. `seed_sha256` tranche, et ces tests fixent l'arbitrage : on actualise
ce qui est resté ce que le seed avait posé, on ne touche pas au reste, et on
n'écrase une édition que sur demande nommant son chemin.
"""

from __future__ import annotations

import pytest

from app.services import agent_workspace as ws


async def _un_chemin_du_modele() -> str:
    return sorted(ws.fichiers_du_modele())[0]


def _etats(rapport: list[dict[str, str]]) -> dict[str, str]:
    return {ligne["path"]: ligne["etat"] for ligne in rapport}


class TestEtatSynchronisation:
    async def test_un_workspace_vide_a_tout_en_absent(self, db_session, test_user):
        rapport = await ws.etat_synchronisation(db_session, test_user.id)
        assert rapport
        assert {ligne["etat"] for ligne in rapport} == {"absent"}

    async def test_un_workspace_fraichement_seede_est_tout_a_jour(self, db_session, test_user):
        await ws.seed(db_session, test_user.id)
        rapport = await ws.etat_synchronisation(db_session, test_user.id)
        assert {ligne["etat"] for ligne in rapport} == {"a_jour"}

    async def test_un_fichier_edite_par_la_personne_diverge(self, db_session, test_user):
        await ws.seed(db_session, test_user.id)
        chemin = await _un_chemin_du_modele()
        await ws.ecrire(db_session, test_user.id, chemin, "ce que j'ai écrit moi-même")

        assert _etats(await ws.etat_synchronisation(db_session, test_user.id))[chemin] == "diverge"

    async def test_un_fichier_reste_au_seed_devient_obsolete(self, db_session, test_user):
        """Le template avance : le fichier n'a pas bougé ici, donc l'actualiser
        ne fait perdre aucun travail. C'est tout l'intérêt de la provenance."""
        await ws.seed(db_session, test_user.id)
        chemin = await _un_chemin_du_modele()
        fichier = await ws.lire(db_session, test_user.id, chemin)
        # Simule un template qui a bougé depuis : le contenu n'est plus celui
        # du modèle, mais il est toujours exactement ce que le seed avait posé.
        fichier.content = "une version ancienne du template"
        fichier.sha256 = ws.calculer_sha256(fichier.content)
        fichier.seed_sha256 = fichier.sha256
        await db_session.flush()

        assert _etats(await ws.etat_synchronisation(db_session, test_user.id))[chemin] == "obsolete"

    async def test_une_provenance_inconnue_est_traitee_comme_une_divergence(
        self, db_session, test_user
    ):
        """L'état de toutes les lignes seedées avant la migration 056. Sans
        provenance, rien ne prouve que le fichier n'a pas été édité : le
        supposer intact donnerait le droit d'écraser du travail réel."""
        await ws.seed(db_session, test_user.id)
        chemin = await _un_chemin_du_modele()
        fichier = await ws.lire(db_session, test_user.id, chemin)
        fichier.content = "une version ancienne du template"
        fichier.sha256 = ws.calculer_sha256(fichier.content)
        fichier.seed_sha256 = None
        await db_session.flush()

        assert _etats(await ws.etat_synchronisation(db_session, test_user.id))[chemin] == "diverge"

    async def test_un_fichier_propre_a_la_personne_n_est_pas_un_ecart(self, db_session, test_user):
        """Le rapport ne parle que des chemins du template. Un fichier que le
        template ne connaît pas est du travail, pas une dérive."""
        await ws.seed(db_session, test_user.id)
        await ws.ecrire(db_session, test_user.id, "shared/mes-notes.md", "à moi")

        chemins = {
            ligne["path"] for ligne in await ws.etat_synchronisation(db_session, test_user.id)
        }
        assert "shared/mes-notes.md" not in chemins

    async def test_ne_modifie_rien(self, db_session, test_user):
        await ws.seed(db_session, test_user.id)
        chemin = await _un_chemin_du_modele()
        avant = (await ws.lire(db_session, test_user.id, chemin)).sha256
        await ws.etat_synchronisation(db_session, test_user.id)
        assert (await ws.lire(db_session, test_user.id, chemin)).sha256 == avant


class TestResynchroniser:
    async def test_les_fichiers_absents_sont_ajoutes(self, db_session, test_user):
        """Le cas mesuré en production : tout le répertoire `agents/` manquait."""
        rapport = await ws.resynchroniser(db_session, test_user.id)
        assert sorted(rapport["ajoutes"]) == sorted(ws.fichiers_du_modele())
        etats = await ws.etat_synchronisation(db_session, test_user.id)
        assert {ligne["etat"] for ligne in etats} == {"a_jour"}

    async def test_un_fichier_reste_au_seed_est_actualise(self, db_session, test_user):
        await ws.seed(db_session, test_user.id)
        chemin = await _un_chemin_du_modele()
        attendu = ws.fichiers_du_modele()[chemin]
        fichier = await ws.lire(db_session, test_user.id, chemin)
        fichier.content = "une version ancienne"
        fichier.sha256 = ws.calculer_sha256(fichier.content)
        fichier.seed_sha256 = fichier.sha256
        await db_session.flush()

        rapport = await ws.resynchroniser(db_session, test_user.id)

        assert rapport["mis_a_jour"] == [chemin]
        assert (await ws.lire(db_session, test_user.id, chemin)).content == attendu

    async def test_une_edition_n_est_jamais_ecrasee_d_office(self, db_session, test_user):
        """Le contrat qui rend la resynchronisation utilisable sans peur."""
        await ws.seed(db_session, test_user.id)
        chemin = await _un_chemin_du_modele()
        await ws.ecrire(db_session, test_user.id, chemin, "ce que j'ai écrit moi-même")

        rapport = await ws.resynchroniser(db_session, test_user.id)

        assert rapport["divergents"] == [chemin]
        assert rapport["adoptes"] == []
        assert (await ws.lire(db_session, test_user.id, chemin)).content == (
            "ce que j'ai écrit moi-même"
        )

    async def test_une_adoption_nommee_reprend_le_template(self, db_session, test_user):
        await ws.seed(db_session, test_user.id)
        chemin = await _un_chemin_du_modele()
        attendu = ws.fichiers_du_modele()[chemin]
        await ws.ecrire(db_session, test_user.id, chemin, "ce que j'ai écrit moi-même")

        rapport = await ws.resynchroniser(db_session, test_user.id, adopter=[chemin])

        assert rapport["adoptes"] == [chemin]
        assert rapport["divergents"] == []
        assert (await ws.lire(db_session, test_user.id, chemin)).content == attendu

    async def test_une_adoption_ne_deborde_pas_sur_les_autres_divergents(
        self, db_session, test_user
    ):
        """Adopter un chemin ne vaut pas adopter tout ce qui diverge."""
        await ws.seed(db_session, test_user.id)
        un, deux = sorted(ws.fichiers_du_modele())[:2]
        await ws.ecrire(db_session, test_user.id, un, "édité")
        await ws.ecrire(db_session, test_user.id, deux, "édité aussi")

        rapport = await ws.resynchroniser(db_session, test_user.id, adopter=[un])

        assert rapport["adoptes"] == [un]
        assert rapport["divergents"] == [deux]
        assert (await ws.lire(db_session, test_user.id, deux)).content == "édité aussi"

    async def test_un_chemin_hors_template_est_refuse(self, db_session, test_user):
        """Adopter n'est pas écrire : le seul contenu que la resynchronisation
        pose vient du template, donc un chemin qu'il ignore n'a pas de sens."""
        await ws.seed(db_session, test_user.id)
        with pytest.raises(ws.WorkspaceError):
            await ws.resynchroniser(db_session, test_user.id, adopter=["shared/inexistant.md"])

    async def test_est_idempotente(self, db_session, test_user):
        await ws.resynchroniser(db_session, test_user.id)
        rapport = await ws.resynchroniser(db_session, test_user.id)
        assert rapport == {"ajoutes": [], "mis_a_jour": [], "adoptes": [], "divergents": []}

    async def test_la_provenance_est_reposee_apres_adoption(self, db_session, test_user):
        """Sinon un fichier adopté resterait divergent pour toujours, et la
        resynchronisation suivante le redemanderait sans fin."""
        await ws.seed(db_session, test_user.id)
        chemin = await _un_chemin_du_modele()
        await ws.ecrire(db_session, test_user.id, chemin, "édité")
        await ws.resynchroniser(db_session, test_user.id, adopter=[chemin])

        assert _etats(await ws.etat_synchronisation(db_session, test_user.id))[chemin] == "a_jour"

    async def test_ne_touche_pas_aux_fichiers_propres_a_la_personne(self, db_session, test_user):
        await ws.seed(db_session, test_user.id)
        await ws.ecrire(db_session, test_user.id, "shared/mes-notes.md", "à moi")

        await ws.resynchroniser(db_session, test_user.id)

        assert (await ws.lire(db_session, test_user.id, "shared/mes-notes.md")).content == "à moi"


class TestProvenanceAuSeed:
    async def test_le_seed_pose_la_provenance(self, db_session, test_user):
        await ws.seed(db_session, test_user.id)
        fichier = await ws.lire(db_session, test_user.id, await _un_chemin_du_modele())
        assert fichier.seed_sha256 == fichier.sha256

    async def test_ecrire_conserve_la_provenance_d_origine(self, db_session, test_user):
        """C'est ce qui permet de distinguer plus tard « édité ici » de
        « template qui a avancé » : la provenance trace d'où le fichier vient,
        pas ce qu'il est devenu."""
        await ws.seed(db_session, test_user.id)
        chemin = await _un_chemin_du_modele()
        origine = (await ws.lire(db_session, test_user.id, chemin)).seed_sha256

        await ws.ecrire(db_session, test_user.id, chemin, "édité")
        fichier = await ws.lire(db_session, test_user.id, chemin)

        assert fichier.seed_sha256 == origine
        assert fichier.sha256 != origine

    async def test_un_fichier_cree_par_la_personne_n_a_pas_de_provenance(
        self, db_session, test_user
    ):
        await ws.ecrire(db_session, test_user.id, "shared/mes-notes.md", "à moi")
        assert (await ws.lire(db_session, test_user.id, "shared/mes-notes.md")).seed_sha256 is None
