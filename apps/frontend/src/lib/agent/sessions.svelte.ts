/**
 * Liste des conversations, partagée entre la barre latérale et les pages.
 *
 * Elle était lue une fois, au montage de la page de liste : une conversation
 * ouverte ensuite n'y apparaissait qu'au rechargement, et la page d'une
 * conversation n'avait pas de liste du tout. Elle vit désormais ici, et chaque
 * création, renommage ou suppression la relit.
 */

import { agentApi, type AgentSession } from '$lib/api/agent';

export const conversations = $state<{
  liste: AgentSession[];
  chargement: boolean;
  echec: boolean;
  /** Conversation affichée, surlignée dans la liste. */
  active: string | null;
  /** Incrémenté à chaque demande de conversation vierge. */
  generation: number;
  /** Liste ouverte en tiroir, sous `lg`, où elle ne tient pas à côté du fil. */
  tiroirOuvert: boolean;
}>({
  liste: [],
  chargement: true,
  echec: false,
  active: null,
  generation: 0,
  tiroirOuvert: false,
});

export async function rafraichirConversations(): Promise<void> {
  try {
    conversations.liste = await agentApi.sessions.list();
    conversations.echec = false;
  } catch {
    // Un échec de lecture ne vide pas la liste déjà affichée : l'utilisateur
    // lirait que son historique a disparu alors que seule la requête a échoué.
    conversations.echec = true;
  } finally {
    conversations.chargement = false;
  }
}

/** Demande une conversation vierge.
 *
 * Nécessaire même quand l'adresse est déjà `/dashboard/chat` : SvelteKit ne
 * remonte pas une page vers laquelle on navigue depuis elle-même, et le panneau
 * gardait alors la conversation précédente. Le message suivant partait dedans,
 * et le nom saisi pour la nouvelle n'était jamais appliqué.
 */
export function nouvelleConversation(): void {
  conversations.generation += 1;
}
