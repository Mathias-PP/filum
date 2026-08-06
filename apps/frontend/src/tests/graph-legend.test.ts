import { describe, expect, it } from 'vitest';
import { legendLabel } from '$lib/components/graph-legend';

describe('legendLabel', () => {
  it('accorde le pluriel au-dela d une fiche', () => {
    expect(legendLabel(2)).toContain('2 fiches Philum reliées');
  });

  it('reste au singulier pour une seule fiche', () => {
    expect(legendLabel(1)).toContain('1 fiche Philum reliée');
  });

  it("n'utilise aucun em-dash", () => {
    expect(legendLabel(3)).not.toContain('—');
  });
});
