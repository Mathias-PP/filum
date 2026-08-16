/**
 * Une source citée doit se voir sans être ouverte.
 *
 * Relevé le 2026-08-16 sur la fiche publiée « Real-world data and clinical
 * experience from over 100,000 multi-cancer early detection tests » : 50
 * sources listées, 14 portant des extraits verbatim, et aucune différence
 * visible entre les deux tant qu'on ne déplie pas les lignes une par une.
 */
import { describe, expect, it } from 'vitest';
import { libelleExtraits } from '$lib/utils/extraits';

describe('libelleExtraits', () => {
  it('ne dit rien quand la source ne porte aucun extrait', () => {
    expect(libelleExtraits(0)).toBeNull();
    expect(libelleExtraits(null)).toBeNull();
    expect(libelleExtraits(undefined)).toBeNull();
  });

  it('reste au singulier pour un seul passage', () => {
    expect(libelleExtraits(1)).toBe('1 extrait');
  });

  it('passe au pluriel au-delà', () => {
    expect(libelleExtraits(2)).toBe('2 extraits');
    expect(libelleExtraits(14)).toBe('14 extraits');
  });
});
