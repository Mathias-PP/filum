import { describe, expect, it } from 'vitest';

import { lireSynthese } from '$lib/utils/synthese';

const A = '11111111-1111-4111-8111-111111111111';
const B = '22222222-2222-4222-8222-222222222222';

describe('synthèse ancrée', () => {
  it('ne rend rien sans texte', () => {
    expect(lireSynthese(null)).toBeNull();
    expect(lireSynthese('   ')).toBeNull();
  });

  it('numérote les extraits dans l’ordre de première apparition', () => {
    const lue = lireSynthese(
      `La taxe a réduit les émissions du transport. [extrait:${B}] Les exemptions ont limité son effet. [extrait:${A}][extrait:${B}]`
    );
    expect(lue?.extraits).toEqual([B, A]);
    expect(lue?.paragraphes[0]).toEqual([
      { texte: 'La taxe a réduit les émissions du transport.', notes: [1] },
      { texte: 'Les exemptions ont limité son effet.', notes: [2, 1] },
    ]);
  });

  it('garde les paragraphes et le texte sans renvoi', () => {
    const lue = lireSynthese(`Premier point. [extrait:${A}]\n\nSecond point, sans renvoi.`);
    expect(lue?.paragraphes).toHaveLength(2);
    expect(lue?.paragraphes[1]).toEqual([{ texte: 'Second point, sans renvoi.', notes: [] }]);
  });
});
