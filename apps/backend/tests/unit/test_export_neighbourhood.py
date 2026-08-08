"""La grammaire des degres, et ce qu'elle refuse.

Le parcours lui-meme se teste en integration (il lui faut une base). Ici, la
seule chose qui puisse se tromper silencieusement : la lecture du parametre.
Un degre rabote plutot que refuse donnerait un export moins profond que
demande, qui se lirait pourtant comme un voisinage complet.
"""

from __future__ import annotations

import pytest

from app.services.export_neighbourhood import MAX_DEGREE, parse_degrees


def test_absent_ne_ramene_aucun_voisin():
    assert parse_degrees(None) == {}
    assert parse_degrees("") == {}


def test_un_entier_ouvre_tous_les_degres_jusque_la():
    degres = parse_degrees("2")
    assert sorted(degres) == [1, 2]
    assert all(d.excerpts and d.archives for d in degres.values())


def test_un_perimetre_par_degre():
    degres = parse_degrees("1:excerpts|2:")
    assert degres[1].excerpts and not degres[1].archives
    assert degres[2].references_only


def test_un_degre_peut_etre_traverse_sans_etre_emporte():
    """« 2:references » sans « 1: » : on veut les voisins des voisins.

    Le parcours doit marcher jusqu'au degre 2 sans rien rapporter du 1.
    """
    degres = parse_degrees("2:")
    assert sorted(degres) == [2]


@pytest.mark.parametrize("spec", ["0", "4", "0:excerpts", f"{MAX_DEGREE + 1}:"])
def test_degre_hors_bornes_refuse(spec):
    with pytest.raises(ValueError, match="hors bornes"):
        parse_degrees(spec)


def test_degre_illisible_refuse():
    with pytest.raises(ValueError, match="illisible"):
        parse_degrees("beaucoup")


def test_section_inconnue_dans_un_degre_refusee():
    with pytest.raises(ValueError, match="Section"):
        parse_degrees("1:fiches-connectees")
