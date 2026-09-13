import { describe, expect, it } from 'vitest';

import { comparerFiches } from '$lib/agent/suiviFiche';
import type { Source } from '$lib/api/types';

function extrait(id: string, texte = 'Une phrase.', verdict: string | null = null) {
  return { id, text: texte, context: null, verified_status: verdict };
}

function source(id: string, extraits: ReturnType<typeof extrait>[] = [], titre = 'Titre'): Source {
  return {
    id,
    title: titre,
    stance: null,
    retraction_status: null,
    oa_status: null,
    archive_status: 'pending',
    annotation: null,
    excerpts: extraits,
  } as unknown as Source;
}

describe('suivi de la fiche en direct', () => {
  it('ne signale rien au premier affichage', () => {
    const ecart = comparerFiches(null, [source('s1', [extrait('e1')])]);
    expect(ecart.cible).toBeNull();
    expect(ecart.sources.size + ecart.extraits.size).toBe(0);
  });

  it('amène l’œil sur l’extrait que l’agent vient d’ajouter', () => {
    const avant = [source('s1', [extrait('e1')]), source('s2')];
    const apres = [source('s1', [extrait('e1')]), source('s2', [extrait('e2')])];
    const ecart = comparerFiches(avant, apres);
    expect(ecart.cible).toEqual({ kind: 'extrait', id: 'e2' });
    expect([...ecart.extraits]).toEqual(['e2']);
    expect([...ecart.sources]).toEqual(['s2']);
  });

  it('amène l’œil sur une source ajoutée sans extrait', () => {
    const ecart = comparerFiches([source('s1')], [source('s1'), source('s2')]);
    expect(ecart.cible).toEqual({ kind: 'source', id: 's2' });
  });

  it('préfère un extrait modifié à une source ajoutée', () => {
    const avant = [source('s1', [extrait('e1', 'Une phrase.', null)])];
    const apres = [source('s1', [extrait('e1', 'Une phrase.', 'found')]), source('s2')];
    expect(comparerFiches(avant, apres).cible).toEqual({ kind: 'extrait', id: 'e1' });
  });

  it('suit une source dont seul le titre a changé', () => {
    const ecart = comparerFiches([source('s1')], [source('s1', [], 'Nouveau titre')]);
    expect(ecart.cible).toEqual({ kind: 'source', id: 's1' });
  });

  it('ne désigne rien quand la fiche n’a pas bougé', () => {
    const lecture = [source('s1', [extrait('e1')])];
    expect(comparerFiches(lecture, [source('s1', [extrait('e1')])]).cible).toBeNull();
  });
});
