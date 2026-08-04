"""Un enum redeclare dans `app/schemas` doit dire la meme chose que celui de
`app/models`.

Vecu le 2026-08-04 : `ArchiveStatus` existait en deux exemplaires. La valeur
`not_applicable` a ete ajoutee au modele et ecrite en base par la migration
024 ; la copie du schema est restee a trois valeurs. Toute fiche contenant une
source concernee a repondu 500 -- et la fiche de demo, qui n'en contenait
aucune, passait : ni la CI ni le premier controle post-deploiement n'ont vu la
panne.

Six autres enums sont dupliques de la meme facon. Ils concordent aujourd'hui ;
rien n'empechait le prochain de deriver. Ce test ne vise donc pas le cas
constate mais la classe entiere, y compris les enums qui n'existent pas encore.

La bonne correction reste de reexporter l'enum du modele plutot que de le
redeclarer -- un alias sort de ce test, puisqu'il n'y a plus deux definitions.
"""

from __future__ import annotations

import importlib
import pkgutil
from enum import Enum

import pytest


def _declared_enums(package: str) -> dict[str, type[Enum]]:
    """Les enums *definis* dans ce paquet. Un simple import n'en est pas un."""
    found: dict[str, type[Enum]] = {}
    root = importlib.import_module(package)
    for info in pkgutil.iter_modules(root.__path__):
        module = importlib.import_module(f"{package}.{info.name}")
        for name, obj in vars(module).items():
            if (
                isinstance(obj, type)
                and issubclass(obj, Enum)
                and obj.__module__ == module.__name__
            ):
                found[name] = obj
    return found


_MODELS = _declared_enums("app.models")
_SCHEMAS = _declared_enums("app.schemas")
_SHARED = sorted(set(_MODELS) & set(_SCHEMAS))


@pytest.mark.parametrize("name", _SHARED)
def test_les_deux_declarations_disent_la_meme_chose(name: str) -> None:
    model_values = {member.value for member in _MODELS[name]}
    schema_values = {member.value for member in _SCHEMAS[name]}
    assert schema_values == model_values, (
        f"{name} diverge entre app/models et app/schemas. Une valeur que la base "
        f"sait ecrire mais que l'API ne sait pas relire est une panne : "
        f"reexportez l'enum du modele au lieu de le redeclarer."
    )
