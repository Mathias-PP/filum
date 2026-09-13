import { describe, expect, it } from 'vitest';

import { appliquer, type ChatItem } from '$lib/agent/conversation';

describe('déroulé guidé', () => {
  it('pose une ligne par étape, et le texte suivant ouvre une bulle neuve', () => {
    let items: ChatItem[] = [{ kind: 'user', text: 'Comment prévenir l’arthrose ?' }];
    items = appliquer(items, {
      type: 'etape_guidee',
      payload: { etape: 'recherche', titre: 'Recherche', rang: 1, total: 5 },
    });
    items = appliquer(items, { type: 'message_delta', payload: { delta: 'Sources.', tour: 1 } });
    items = appliquer(items, {
      type: 'etape_guidee',
      payload: { etape: 'sources', titre: 'Sources', rang: 2, total: 5 },
    });
    items = appliquer(items, { type: 'message_delta', payload: { delta: 'Ajoutées.', tour: 2 } });

    expect(items.map((i) => i.kind)).toEqual(['user', 'etape', 'assistant', 'etape', 'assistant']);
    expect(items[3]).toEqual({ kind: 'etape', titre: 'Sources', rang: 2, total: 5 });
  });
});
