import { describe, expect, it } from 'vitest';

import { appliquer, depuisMessages, type ChatItem } from '$lib/agent/conversation';
import type { AgentEvent, AgentMessage } from '$lib/api/agent';

function replier(evenements: AgentEvent[], depart: ChatItem[] = []): ChatItem[] {
  return evenements.reduce(appliquer, depart);
}

describe('repli des événements de l’agent', () => {
  it('recolle les fragments de réponse dans une seule bulle', () => {
    const items = replier([
      { type: 'message_delta', payload: { delta: 'Bon', tour: 1 } },
      { type: 'message_delta', payload: { delta: 'jour.', tour: 1 } },
    ]);
    expect(items).toEqual([{ kind: 'assistant', text: 'Bonjour.' }]);
  });

  it('ne recolle pas par-dessus un outil intercalé', () => {
    const items = replier([
      { type: 'message_delta', payload: { delta: 'Je cherche.', tour: 1 } },
      {
        type: 'tool_call',
        payload: { id: 'call_1', name: 'web_search', arguments: { q: 'x' }, tour: 1 },
      },
      { type: 'message_delta', payload: { delta: 'Voilà.', tour: 2 } },
    ]);
    expect(items.map((i) => i.kind)).toEqual(['assistant', 'tool', 'assistant']);
  });

  it('rattache un résultat à son appel d’outil', () => {
    const items = replier([
      {
        type: 'tool_call',
        payload: { id: 'call_1', name: 'web_search', arguments: {}, tour: 1 },
      },
      { type: 'tool_result', payload: { id: 'call_1', name: 'web_search', result: { ok: true } } },
    ]);
    expect(items[0]).toMatchObject({ kind: 'tool', result: { ok: true } });
  });

  it('ignore un résultat sans appel correspondant', () => {
    const items = replier([
      { type: 'tool_result', payload: { id: 'inconnu', name: 'web_search', result: {} } },
    ]);
    expect(items).toEqual([]);
  });

  it('tranche la carte d’approbation que l’événement désigne', () => {
    const items = replier([
      {
        type: 'approval_request',
        payload: { request_id: 'r1', tool: 'publish_card', arguments: {}, tour: 1 },
      },
      {
        type: 'approval_request',
        payload: { request_id: 'r2', tool: 'delete_card', arguments: {}, tour: 1 },
      },
      {
        type: 'approval_resolved',
        payload: { request_id: 'r1', tool: 'publish_card', approved: true },
      },
    ]);
    expect(items[0]).toMatchObject({ kind: 'approval', requestId: 'r1', approved: true });
    expect(items[1]).toMatchObject({ kind: 'approval', requestId: 'r2', approved: null });
  });

  it('affiche une erreur sans effacer ce qui précède', () => {
    const items = replier([
      { type: 'message_delta', payload: { delta: 'Bonjour.', tour: 1 } },
      { type: 'error', payload: { message: 'Le provider a répondu HTTP 401' } },
    ]);
    expect(items.map((i) => i.kind)).toEqual(['assistant', 'error']);
  });

  it('n’ajoute rien pour `session` et `done`', () => {
    const items = replier([
      { type: 'session', payload: { id: 'abc' } },
      { type: 'done', payload: { reason: 'complete' } },
    ]);
    expect(items).toEqual([]);
  });

  it('clôture un appel resté sans résultat quand le flux se termine', () => {
    const items = replier([
      {
        type: 'tool_call',
        payload: { id: 'call_1', name: 'web_search', arguments: {}, tour: 1 },
      },
      { type: 'done', payload: { reason: 'complete' } },
    ]);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      kind: 'tool',
      name: 'web_search',
      result: { error: expect.stringContaining('sans réponse') },
    });
  });

  it('clôture les appels en vol quand une erreur survient', () => {
    const items = replier([
      {
        type: 'tool_call',
        payload: { id: 'call_1', name: 'fs_read', arguments: {}, tour: 1 },
      },
      { type: 'error', payload: { message: 'provider injoignable' } },
    ]);
    const carte = items[0] as Extract<ChatItem, { kind: 'tool' }>;
    expect(carte.result).toEqual({ error: expect.stringContaining('sans réponse') });
    expect(items.map((i) => i.kind)).toEqual(['tool', 'error']);
  });
});

describe('rehydratation d’une session persistée', () => {
  const message = (partiel: Partial<AgentMessage>): AgentMessage => ({
    id: 'm1',
    role: 'user',
    content: '',
    tool_calls: null,
    tool_name: null,
    created_at: '2026-08-20T10:00:00',
    ...partiel,
  });

  it('réapparie chaque résultat à son appel d’origine via tool_call_id', () => {
    const items = depuisMessages([
      message({ id: 'm1', role: 'user', content: 'cherche' }),
      message({
        id: 'm2',
        role: 'assistant',
        content: '',
        tool_calls: [
          { id: 'call_1', function: { name: 'fs_read', arguments: '{"path":"a.md"}' } },
          { id: 'call_2', function: { name: 'fs_list', arguments: '{}' } },
        ],
      }),
      message({
        id: 'm3',
        role: 'tool',
        tool_name: 'fs_list',
        tool_call_id: 'call_2',
        content: '{"entries":[]}',
      }),
      message({
        id: 'm4',
        role: 'tool',
        tool_name: 'fs_read',
        tool_call_id: 'call_1',
        content: '{"found":true}',
      }),
      message({ id: 'm5', role: 'assistant', content: 'voilà' }),
    ]);
    expect(items.map((i) => i.kind)).toEqual(['user', 'tool', 'tool', 'assistant']);
    expect(items[1]).toMatchObject({
      kind: 'tool',
      id: 'call_1',
      name: 'fs_read',
      args: { path: 'a.md' },
      result: { found: true },
    });
    expect(items[2]).toMatchObject({
      kind: 'tool',
      id: 'call_2',
      name: 'fs_list',
      args: {},
      result: { entries: [] },
    });
  });

  it('réapparie à l’ancienne (par nom) les lignes sans identifiant', () => {
    const items = depuisMessages([
      message({
        id: 'm1',
        role: 'assistant',
        content: '',
        tool_calls: [{ function: { name: 'web_search', arguments: '{"q":"x"}' } }],
      }),
      message({ id: 'm2', role: 'tool', tool_name: 'web_search', content: '{"ok":1}' }),
    ]);
    expect(items).toEqual([
      {
        kind: 'tool',
        id: 'm1',
        name: 'web_search',
        args: { q: 'x' },
        result: { ok: 1 },
      },
    ]);
  });

  it('montre un échec explicite pour un appel jamais abouti dans le journal', () => {
    const items = depuisMessages([
      message({
        id: 'm1',
        role: 'assistant',
        content: '',
        tool_calls: [{ id: 'call_9', function: { name: 'publish_card', arguments: '{}' } }],
      }),
    ]);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      kind: 'tool',
      name: 'publish_card',
      result: { error: expect.stringContaining('sans réponse') },
    });
  });

  it('ne fabrique pas de bulle vide pour un assistant sans texte ni outil', () => {
    expect(depuisMessages([message({ role: 'assistant', content: '' })])).toEqual([]);
  });
});
