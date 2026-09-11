import { describe, expect, it } from 'vitest';

import { regrouper, resumerActivite, type BlocActivite } from '$lib/agent/activite';
import { analyser } from '$lib/agent/markdown';
import type { ChatItem } from '$lib/agent/conversation';

function outil(id: string, name: string, result: Record<string, unknown> | null = {}): ChatItem {
  return { kind: 'tool', id, name, args: {}, result };
}

describe('blocs d’activité', () => {
  it('replie une suite d’appels en un seul bloc, et groupe les appels répétés', () => {
    const rendu = regrouper([
      { kind: 'user', text: 'Nettoie la fiche' },
      outil('1', 'get_source'),
      outil('2', 'delete_excerpt'),
      outil('3', 'delete_excerpt', { error: 'refusé' }),
      outil('4', 'get_source', null),
      { kind: 'assistant', text: 'Fait.' },
    ]);
    expect(rendu.map((r) => r.kind)).toEqual(['user', 'activite', 'assistant']);
    const bloc = rendu[1] as BlocActivite;
    expect(bloc.groupes.map((g) => [g.name, g.entrees.length])).toEqual([
      ['get_source', 1],
      ['delete_excerpt', 2],
      ['get_source', 1],
    ]);
    expect(bloc).toMatchObject({ total: 4, echecs: 1, enCours: 1 });
  });

  it('résume le bloc en une phrase, sans nom technique', () => {
    const [bloc] = regrouper([
      outil('1', 'get_source'),
      outil('2', 'get_source'),
      outil('3', 'delete_excerpt'),
    ]) as BlocActivite[];
    expect(resumerActivite(bloc)).toBe('3 actions : lit 2 sources, supprime un extrait');
  });

  it('nomme trois outils au plus et compte les autres', () => {
    const [bloc] = regrouper([
      outil('1', 'get_source'),
      outil('2', 'fetch_url'),
      outil('3', 'web_search'),
      outil('4', 'get_card'),
      outil('5', 'list_sources'),
    ]) as BlocActivite[];
    expect(resumerActivite(bloc)).toMatch(/^5 actions : .+ et 2 autres$/);
  });

  it('dit simplement l’action quand le bloc n’en contient qu’une', () => {
    const [bloc] = regrouper([outil('1', 'get_source')]) as BlocActivite[];
    expect(resumerActivite(bloc)).toBe('Lit la source');
  });
});

describe('tableaux markdown', () => {
  it('reconnaît un tableau et le garde rectangulaire', () => {
    const [tableau] = analyser(
      ['| Source | Statut |', '|---|:---:|', '| Wakefield | **rétractée** |', '| Seule |'].join(
        '\n'
      )
    );
    expect(tableau.t).toBe('tableau');
    if (tableau.t !== 'tableau') return;
    expect(tableau.entetes).toHaveLength(2);
    expect(tableau.lignes).toHaveLength(2);
    expect(tableau.lignes[0][1]).toEqual([{ t: 'gras', texte: 'rétractée' }]);
    expect(tableau.lignes[1]).toHaveLength(2);
  });

  it('laisse en paragraphe une barre verticale isolée', () => {
    const blocs = analyser('Choix A | choix B, sans tableau.');
    expect(blocs.map((b) => b.t)).toEqual(['paragraphe']);
  });
});
