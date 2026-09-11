import { describe, expect, it } from 'vitest';

import { depuisMessages } from '$lib/agent/conversation';
import { rendreGroupe, rendreOutil } from '$lib/agent/toolLabels';
import type { AgentMessage } from '$lib/api/agent';

describe('libellés des outils', () => {
  it('dit ce que fait l’outil au lieu d’afficher son nom technique', () => {
    expect(rendreOutil('get_my_card', { slug: 'la-fiche' }).action).toBe('Lit votre fiche');
  });

  it('n’affiche jamais un nom à tiret bas, même pour un outil inconnu', () => {
    const rendu = rendreOutil('outil_tout_neuf', {});
    expect(rendu.action).not.toContain('_');
    expect(rendu.action).toContain('outil tout neuf');
  });

  it('nomme un groupe d’appels au pluriel', () => {
    expect(rendreGroupe('delete_excerpt', 10)).toBe('Supprime 10 extraits');
  });

  it('compte un groupe d’outil sans pluriel connu sans nom technique', () => {
    const libelle = rendreGroupe('outil_tout_neuf', 3);
    expect(libelle).not.toContain('_');
    expect(libelle).toContain('3');
  });
});

describe('conversation rouverte pendant que le serveur termine', () => {
  const messages: AgentMessage[] = [
    {
      id: 'm1',
      role: 'user',
      content: 'Lis la source',
      tool_calls: null,
      tool_name: null,
      created_at: '2026-09-11T10:00:00',
    },
    {
      id: 'm2',
      role: 'assistant',
      content: '',
      tool_calls: [{ id: 'c1', function: { name: 'get_source', arguments: '{}' } }],
      tool_name: null,
      created_at: '2026-09-11T10:00:01',
    },
  ];

  it('laisse en cours un appel encore sans résultat', () => {
    const [, outil] = depuisMessages(messages, { clore: false });
    expect(outil).toMatchObject({ kind: 'tool', result: null });
  });

  it('clôt par défaut un appel resté sans résultat', () => {
    const [, outil] = depuisMessages(messages);
    expect(outil).toMatchObject({ kind: 'tool' });
    expect((outil as { result: Record<string, unknown> }).result).toHaveProperty('error');
  });
});
