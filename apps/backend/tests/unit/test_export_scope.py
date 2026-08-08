"""Le perimetre d'export : ce qu'on emporte, et ce qu'on refuse d'emporter.

Deux proprietes tiennent tout le module :

1. **Le defaut ne retire rien.** Un lien d'export deja en circulation doit
   continuer a rendre ce qu'il rendait. C'est pourquoi `include` absent vaut
   « tout », et non « le minimum ».
2. **Une cle inconnue est une erreur, pas un silence.** Une faute de frappe qui
   retirerait discretement une section produirait un export incomplet dont
   personne ne verrait qu'il l'est.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.services.export_scope import FULL, SECTIONS, ExportScope, parse_scope


def test_parametre_absent_emporte_tout():
    assert parse_scope(None) == FULL
    assert all(getattr(FULL, cle) for cle in SECTIONS)


def test_parametre_vide_ne_garde_que_les_references():
    scope = parse_scope("")
    assert scope.references_only
    assert not any(getattr(scope, cle) for cle in SECTIONS)


def test_selection_partielle():
    scope = parse_scope("excerpts,archives")
    assert scope.excerpts and scope.archives
    assert not scope.annotations and not scope.reliability
    assert not scope.references_only


def test_espaces_et_virgules_superflues_tolerees():
    assert parse_scope(" excerpts , , archives ") == parse_scope("excerpts,archives")


def test_section_inconnue_est_refusee():
    # Une cle ignoree silencieusement donnerait un export ampute sans qu'on le
    # sache : le refus est le seul comportement honnete.
    with pytest.raises(ValueError, match="fiches-connectees"):
        parse_scope("excerpts,fiches-connectees")


def test_le_perimetre_est_immuable():
    # Fige : un perimetre passe a plusieurs formats ne doit pas pouvoir etre
    # modifie par l'un d'eux en cours de route.
    with pytest.raises(dataclasses.FrozenInstanceError):
        ExportScope().excerpts = False  # type: ignore[misc]
