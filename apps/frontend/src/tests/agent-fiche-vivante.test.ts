import { describe, expect, it } from 'vitest';

import type { ChatItem } from '$lib/agent/conversation';
import { appelsTermines, slugFicheCourante } from '$lib/agent/ficheCourante';

function outil(
  name: string,
  args: Record<string, unknown>,
  result: Record<string, unknown> | null = {}
): ChatItem {
  return { kind: 'tool', id: `${name}-${Math.random()}`, name, args, result };
}

describe('fiche sur laquelle l’agent travaille', () => {
  it('est la dernière qu’un outil a nommée', () => {
    const items: ChatItem[] = [
      outil('get_my_card', { card_slug: 'ancienne' }),
      { kind: 'assistant', text: 'Je passe à la suivante.' },
      outil('add_source', { card_slug: 'warburg' }, { card_slug: 'warburg', title: 'Une source' }),
      outil('fetch_url', { url: 'https://exemple.org' }),
    ];
    expect(slugFicheCourante(items)).toBe('warburg');
  });

  it('lit le slug d’une fiche tout juste créée dans le résultat', () => {
    expect(slugFicheCourante([outil('create_card', { title: 'X' }, { slug: 'nouvelle' })])).toBe(
      'nouvelle'
    );
  });

  it('ne se fie pas à un appel en échec', () => {
    const items: ChatItem[] = [
      outil('get_my_card', { card_slug: 'bonne' }),
      outil('get_my_card', { card_slug: 'inexistante' }, { error: 'Fiche introuvable' }),
    ];
    expect(slugFicheCourante(items)).toBe('bonne');
  });

  it('rend null tant qu’aucune fiche n’est nommée', () => {
    expect(slugFicheCourante([outil('web_search', { query: 'warburg' })])).toBeNull();
  });
});

describe('déclencheur de relecture', () => {
  it('compte les appels terminés, pas ceux en cours', () => {
    expect(
      appelsTermines([outil('a', {}), outil('b', {}, null), outil('c', {}, { error: 'x' })])
    ).toBe(2);
  });
});
