from __future__ import annotations

from uuid import uuid4

from app.models.source_excerpt import SourceExcerpt
from app.services.embeddings import empreinte, texte_a_embedder
from app.services.excerpt_indexing import a_reindexer


def _extrait(text: str = "Un passage cite.", **kwargs) -> SourceExcerpt:
    e = SourceExcerpt(text=text, **kwargs)
    e.id = uuid4()
    return e


class TestAReindexer:
    def test_extrait_jamais_indexe_est_a_faire(self):
        e = _extrait()
        assert a_reindexer([e], {}) == [e]

    def test_extrait_inchange_est_laisse_tranquille(self):
        e = _extrait()
        deja = {e.id: empreinte(texte_a_embedder(e))}
        assert a_reindexer([e], deja) == []

    def test_verbatim_reformule_repasse(self):
        e = _extrait()
        deja = {e.id: empreinte("un autre texte")}
        assert a_reindexer([e], deja) == [e]

    def test_intitule_change_repasse(self):
        # L'empreinte porte sur ce qui est soumis au modele, intitule compris :
        # changer l'etiquette change le vecteur.
        e = _extrait(title="Cout energetique")
        avant = empreinte(texte_a_embedder(_extrait(title="Autre chose")))
        assert a_reindexer([e], {e.id: avant}) == [e]

    def test_extrait_vide_est_ignore(self):
        e = _extrait(text="   ")
        assert a_reindexer([e], {}) == []

    def test_seuls_les_extraits_concernes_ressortent(self):
        inchange = _extrait(text="Deja indexe.")
        nouveau = _extrait(text="Jamais indexe.")
        deja = {inchange.id: empreinte(texte_a_embedder(inchange))}
        assert a_reindexer([inchange, nouveau], deja) == [nouveau]

    def test_empreinte_d_un_autre_extrait_ne_dispense_pas(self):
        e = _extrait()
        autre = _extrait(text="Autre passage.")
        deja = {autre.id: empreinte(texte_a_embedder(e))}
        assert a_reindexer([e], deja) == [e]
