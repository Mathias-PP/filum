import { describe, expect, it } from 'vitest';

import { cardNodeLabel } from '$lib/utils/card-label';

/**
 * Le contrat de `cardNodeLabel` est **inversé** par rapport à sa version
 * historique : on ne retombe **jamais** sur le créateur Philum. Le fallback
 * créateur a été ajouté puis retiré plusieurs fois — chaque réapparition a
 * produit le même bug (fiche seed « Early detection of multiple cancers » qui
 * affichait « Mathias » comme auteur sur le graphe alors qu'il n'a rien écrit
 * de l'article). Ces tests figent le contrat : `authors → title → rien`,
 * jamais le créateur.
 *
 * Voir aussi PR #448 (règle symétrique pour la meta `citation_author`).
 */
describe('cardNodeLabel', () => {
  it('affiche les auteurs du contenu quand ils sont déclarés', () => {
    expect(cardNodeLabel({ authors: 'Dubois, C.; Martin, P.', title: 'Ma fiche' })).toBe(
      'Dubois, C.; Martin, P.'
    );
  });

  it('retombe sur le titre quand les auteurs manquent, jamais sur un créateur', () => {
    expect(cardNodeLabel({ authors: null, title: 'Une fiche sans auteur déclaré' })).toBe(
      'Une fiche sans auteur déclaré'
    );
    expect(cardNodeLabel({ authors: '   ', title: 'Autre fiche' })).toBe('Autre fiche');
  });

  it('rend une chaîne vide quand ni auteurs ni titre ne sont connus', () => {
    // Cas dégénéré : aucun affichage vaut mieux qu'une invention.
    expect(cardNodeLabel({ authors: null, title: null })).toBe('');
    expect(cardNodeLabel({})).toBe('');
  });

  it("n'invente pas d'auteur pour une fiche seed non renseignée", () => {
    // Le vrai cas produit : « Early detection of multiple cancers » chez
    // mathias-pinault, is_seed=true, content_authors=null. Avant fix : le
    // graphe affichait « Mathias ». Depuis : il affiche le titre du contenu.
    expect(
      cardNodeLabel({
        authors: null,
        title: 'Early detection of multiple cancers: the era of methylation-based liquid biopsy',
      })
    ).toBe('Early detection of multiple cancers: the era of methylation-based liquid biopsy');
  });
});
