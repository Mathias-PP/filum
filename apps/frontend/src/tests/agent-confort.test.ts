import { describe, expect, it } from 'vitest';

import { filtrerConversations, grouperParDate } from '$lib/agent/groupesDates';

const MAINTENANT = new Date(2026, 8, 11, 15, 0, 0);

function session(title: string, joursAvant: number) {
  const quand = new Date(MAINTENANT.getTime() - joursAvant * 86_400_000);
  return { title, created_at: quand.toISOString(), last_message_at: quand.toISOString() };
}

describe('conversations groupées par date', () => {
  it('range chaque conversation dans sa tranche, et omet les tranches vides', () => {
    const groupes = grouperParDate(
      [
        session('ce matin', 0),
        session('hier soir', 1),
        session('la semaine', 4),
        session('vieux', 90),
      ],
      MAINTENANT
    );
    expect(groupes.map((g) => [g.libelle, g.sessions.map((s) => s.title)])).toEqual([
      ['Aujourd’hui', ['ce matin']],
      ['Hier', ['hier soir']],
      ['7 derniers jours', ['la semaine']],
      ['Plus ancien', ['vieux']],
    ]);
  });

  it('lit une date du serveur écrite sans fuseau comme de l’UTC', () => {
    const [groupe] = grouperParDate(
      [{ title: 'naïve', last_message_at: '2026-09-11T12:00:00' }],
      MAINTENANT
    );
    expect(groupe.libelle).toBe('Aujourd’hui');
  });

  it('range en fin de liste une conversation sans date lisible', () => {
    const [groupe] = grouperParDate([{ title: 'sans date', last_message_at: null }], MAINTENANT);
    expect(groupe.libelle).toBe('Plus ancien');
  });
});

describe('recherche dans les conversations', () => {
  const liste = [session('Effet Warburg', 0), session('Tyrosine et cognition', 0)];

  it('ignore les accents et la casse', () => {
    expect(filtrerConversations(liste, 'warbûrg').map((s) => s.title)).toEqual(['Effet Warburg']);
  });

  it('rend tout quand la recherche est vide', () => {
    expect(filtrerConversations(liste, '  ')).toHaveLength(2);
  });
});
