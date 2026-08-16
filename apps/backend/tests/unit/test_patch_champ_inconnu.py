"""Une modification qui porte sur un champ inexistant doit etre refusee.

Mesure du 2026-08-16, en marquant six sources cles sur une fiche : le PATCH
envoyait `is_key_source`, alors que le champ se nomme `is_pivot`. L'API a
repondu `200 OK` six fois de suite, sans rien ecrire et sans rien dire. Rien
dans la reponse ne distinguait la reussite de l'echec ; c'est en relisant la
fiche publiee qu'on voyait zero source cle.

Pydantic ignore les champs surnumeraires par defaut. Sur un schema de mise a
jour, ou tous les champs sont facultatifs, cela veut dire qu'un corps
entierement faux vaut un corps vide : la requete « reussit » toujours.

L'enjeu depasse la coquille de frappe. Philum expose un serveur MCP et se
presente comme une infrastructure ouverte : un agent qui devine un nom de
champ doit s'entendre dire qu'il se trompe, pas recevoir un 200.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.biblio_card import CardUpdate
from app.schemas.source import SourceUpdate


def test_un_champ_inconnu_sur_une_source_est_refuse():
    with pytest.raises(ValidationError) as e:
        SourceUpdate(is_key_source=True)

    assert "is_key_source" in str(e.value)


def test_un_champ_inconnu_sur_une_fiche_est_refuse():
    with pytest.raises(ValidationError) as e:
        CardUpdate(published=True)

    assert "published" in str(e.value)


def test_les_champs_connus_passent_toujours():
    #: Le garde-fou ne doit rien couter aux appels legitimes : c'est
    #: exactement le corps que le formulaire de source envoie.
    maj = SourceUpdate(title="Cancer statistics, 2024", is_pivot=True, doi="10.3322/caac.21820")

    assert maj.is_pivot is True
    assert maj.doi == "10.3322/caac.21820"


def test_une_modification_vide_reste_permise():
    #: Un corps vide ne modifie rien, mais il n'est pas une erreur : c'est
    #: ainsi que le client demande un simple rafraichissement.
    assert SourceUpdate().model_dump(exclude_unset=True) == {}


def test_l_url_reste_hors_de_portee_d_une_modification():
    #: `url` est volontairement absent du schema : changer l'adresse d'une
    #: source detacherait son archive Wayback de ce qu'elle atteste. Le
    #: refus doit desormais etre dit, la ou il etait silencieux.
    with pytest.raises(ValidationError):
        SourceUpdate(url="https://exemple.org/autre-page")
