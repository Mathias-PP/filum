import { describe, expect, it } from 'vitest';

import { annoterTours, bilanDesAppels, regrouper, type AppelOutil } from '$lib/agent/activite';

let rang = 0;
function outil(
  name: string,
  result: Record<string, unknown> | null = {},
  args: Record<string, unknown> = {}
): AppelOutil {
  rang += 1;
  return { kind: 'tool', id: `${name}-${rang}`, name, args, result };
}

describe('bilan d’un tour', () => {
  it('compte ce que les outils ont réellement écrit, et les refus', () => {
    const bilan = bilanDesAppels([
      outil('get_source'),
      outil('add_sources_batch', {}, { sources: [{}, {}] }),
      outil('add_excerpt'),
      outil('add_excerpt'),
      outil('add_excerpt', { error: 'absent de la source' }),
      outil('add_excerpt', { error: 'absent de la source' }),
      outil('add_excerpt', { error: 'absent de la source' }),
    ]);
    expect(bilan).toBe('Bilan : 2 sources ajoutées, 2 extraits posés, 3 extraits refusés.');
  });

  it('compte les sources et les extraits posés par un seul appel à retenir', () => {
    const bilan = bilanDesAppels([
      outil('retenir', { sources_ajoutees: 2, extraits_poses: 5 }),
      outil('retenir', { error: 'Aucun extrait posé', sources_ajoutees: 0, extraits_poses: 0 }),
    ]);
    expect(bilan).toBe('Bilan : 2 sources ajoutées, 5 extraits posés, 1 écriture en échec.');
  });

  it('ne dit rien d’un tour qui n’a rien tenté d’écrire', () => {
    expect(bilanDesAppels([outil('get_source'), outil('web_search')])).toBeNull();
  });

  it('ignore un appel encore sans résultat', () => {
    expect(bilanDesAppels([outil('add_excerpt', null)])).toBeNull();
  });
});

describe('annotation des tours', () => {
  const long = 'Pour prévenir l’arthrose, il faut surveiller son poids. '.repeat(6);

  it('pose le bilan sur la dernière réponse, et marque une réponse longue sans lecture', () => {
    const affichables = regrouper([
      { kind: 'user', text: 'Ajoute un extrait' },
      { kind: 'assistant', text: 'Je lis la page.' },
      outil('add_excerpt'),
      { kind: 'assistant', text: 'Fait.' },
      { kind: 'user', text: 'Comment prévenir l’arthrose ?' },
      { kind: 'assistant', text: long },
      { kind: 'user', text: 'Merci' },
      { kind: 'assistant', text: 'Avec plaisir.' },
    ]);
    const notes = annoterTours(affichables);
    expect(notes.get(3)).toEqual({ bilan: 'Bilan : 1 extrait posé.', sansSource: false });
    expect(notes.has(1)).toBe(false);
    expect(notes.get(5)).toEqual({ bilan: null, sansSource: true });
    expect(notes.has(7)).toBe(false);
  });
});
