/**
 * Ce que l'espace d'édition a le droit d'affirmer du juge de fidélité.
 *
 * Comme pour la relecture de citation, le risque n'est pas le plantage : c'est
 * de dire un peu plus que ce qu'on sait. Quatre confusions à empêcher, chacune
 * tenue par un test : « jamais jugé » ne doit pas se lire comme « validé », une
 * valeur hors vocabulaire ne doit pas se rapprocher de la plus proche, la
 * portée du jugement doit être dite, et rien de tout cela ne doit ressembler à
 * un score.
 */
import { describe, expect, it } from 'vitest';
import {
  AVERTISSEMENT_NON_MESURE,
  CLASSES_FIDELITE,
  lireFidelite,
  parExtrait,
  type FideliteVerdict,
} from '$lib/utils/fidelite-verdict';

function verdict(p: Partial<FideliteVerdict> = {}): FideliteVerdict {
  return {
    excerpt_id: 'e1',
    source_id: 's1',
    verdict: null,
    scope: null,
    checked_at: null,
    note: null,
    ...p,
  };
}

describe('lireFidelite', () => {
  it("dit qu'un extrait n'a jamais été relu, au lieu de se taire", () => {
    const lu = lireFidelite(verdict());
    expect(lu.label).toBe('Jamais relu par le juge');
    expect(lu.ton).toBe('inconnu');
  });

  it('distingue un accord de la source d’un désaccord', () => {
    expect(lireFidelite(verdict({ verdict: 'soutient' })).ton).toBe('accord');
    expect(lireFidelite(verdict({ verdict: 'contredit' })).ton).toBe('desaccord');
    expect(lireFidelite(verdict({ verdict: 'mixte' })).ton).toBe('desaccord');
  });

  it("ne reproche rien à la citation quand il n'y avait pas de quoi trancher", () => {
    const lu = lireFidelite(verdict({ verdict: 'preuve_insuffisante' }));
    expect(lu.ton).toBe('inconnu');
    expect(lu.detail).toContain("n'est pas un reproche");
  });

  it('dit sur quoi le juge s’est prononcé', () => {
    const integral = lireFidelite(verdict({ verdict: 'soutient', scope: 'texte_integral' }));
    const sansTexte = lireFidelite(verdict({ verdict: 'contredit', scope: 'metadonnees_seules' }));
    expect(integral.detail).toContain('texte intégral');
    expect(sansTexte.detail).toContain('sans le texte de la source');
  });

  it("n'arrondit pas une valeur inconnue vers la plus proche", () => {
    const lu = lireFidelite(verdict({ verdict: 'plutot favorable' }));
    expect(lu.label).toBe('Verdict non reconnu');
    expect(lu.ton).toBe('inconnu');
  });

  it('reprend la phrase du juge quand il en a donné une', () => {
    const lu = lireFidelite(
      verdict({ verdict: 'contredit', note: 'le passage porte sur une autre espèce' })
    );
    expect(lu.detail).toContain('une autre espèce');
  });
});

describe('parExtrait', () => {
  it('indexe le rapport par citation', () => {
    const index = parExtrait({
      actif: true,
      cle_configuree: true,
      en_attente: 1,
      verdicts: [verdict({ excerpt_id: 'a' }), verdict({ excerpt_id: 'b', verdict: 'soutient' })],
      avertissement: AVERTISSEMENT_NON_MESURE,
    });
    expect(Object.keys(index).sort()).toEqual(['a', 'b']);
    expect(index.b.verdict).toBe('soutient');
  });
});

describe('le vocabulaire', () => {
  it('ne porte aucun score : un scalaire inviterait à la moyenne', () => {
    const rendus = ['soutient', 'contredit', 'mixte', 'ne_traite_pas', 'ambigu'].map((v) =>
      lireFidelite(verdict({ verdict: v }))
    );
    for (const lu of rendus) {
      expect(lu.label).not.toMatch(/\d/);
      expect(lu.label).not.toContain('%');
    }
  });

  it('annonce en clair que le juge n’a pas été mesuré', () => {
    expect(AVERTISSEMENT_NON_MESURE).toContain('mesuré');
    expect(AVERTISSEMENT_NON_MESURE).toContain('pas une preuve');
  });

  it('a une classe pour chaque ton', () => {
    expect(Object.keys(CLASSES_FIDELITE).sort()).toEqual(['accord', 'desaccord', 'inconnu']);
  });
});
