/**
 * Conversations groupées par date, et filtrées par une recherche.
 *
 * Vingt-quatre conversations en une seule liste, sans repère : on ne
 * retrouvait la sienne qu'en relisant tous les titres.
 */

export interface ConversationDatee {
  title: string;
  created_at?: string | null;
  last_message_at?: string | null;
}

export interface GroupeConversations<T> {
  libelle: string;
  sessions: T[];
}

const JOUR = 86_400_000;

/** Les dates du serveur sont en UTC, sans fuseau écrit. */
function instant(brut: string | null | undefined): number {
  if (!brut) return Number.NaN;
  return Date.parse(/[zZ]$|[+-]\d\d:\d\d$/.test(brut) ? brut : `${brut}Z`);
}

export function grouperParDate<T extends ConversationDatee>(
  sessions: T[],
  maintenant: Date = new Date()
): GroupeConversations<T>[] {
  const debutDuJour = new Date(
    maintenant.getFullYear(),
    maintenant.getMonth(),
    maintenant.getDate()
  ).getTime();
  const tranches = [
    { libelle: 'Aujourd’hui', depuis: debutDuJour },
    { libelle: 'Hier', depuis: debutDuJour - JOUR },
    { libelle: '7 derniers jours', depuis: debutDuJour - 7 * JOUR },
    { libelle: '30 derniers jours', depuis: debutDuJour - 30 * JOUR },
  ];
  const groupes: GroupeConversations<T>[] = [
    ...tranches.map((t) => ({ libelle: t.libelle, sessions: [] as T[] })),
    { libelle: 'Plus ancien', sessions: [] as T[] },
  ];
  for (const session of sessions) {
    const quand = instant(session.last_message_at ?? session.created_at);
    const rang = tranches.findIndex((t) => quand >= t.depuis);
    // Une date illisible range la conversation en fin de liste, jamais nulle part.
    groupes[rang === -1 ? groupes.length - 1 : rang].sessions.push(session);
  }
  return groupes.filter((g) => g.sessions.length > 0);
}

function normaliser(texte: string): string {
  return texte
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

/** Filtre sur le titre, sans tenir compte des accents ni de la casse. */
export function filtrerConversations<T extends ConversationDatee>(
  sessions: T[],
  recherche: string
): T[] {
  const cherche = normaliser(recherche);
  if (!cherche) return sessions;
  return sessions.filter((s) => normaliser(s.title).includes(cherche));
}
