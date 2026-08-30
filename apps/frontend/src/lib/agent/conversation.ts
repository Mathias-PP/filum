/**
 * Repli des événements SSE de l'agent en une liste affichable.
 *
 * Le flux est une suite d'événements, pas une conversation : un `tool_result`
 * doit rejoindre le `tool_call` qui l'a demandé, un `approval_resolved` la
 * carte d'approbation qu'il tranche. Ce repli est une fonction pure pour
 * qu'on puisse le tester sans navigateur ni réseau.
 */

import type { AgentEvent, AgentMessage } from '$lib/api/agent';

export type ChatItem =
  | { kind: 'user'; text: string }
  | { kind: 'assistant'; text: string }
  | {
      kind: 'tool';
      id: string;
      name: string;
      args: Record<string, unknown>;
      result: Record<string, unknown> | null;
    }
  | {
      kind: 'approval';
      requestId: string;
      tool: string;
      args: Record<string, unknown>;
      /** Résumé lisible calculé par le serveur (résout UUIDs → titres). */
      resume?: string;
      /** Époque (secondes) d'expiration de la demande, si le serveur la fournit. */
      expiresAt?: number;
      approved: boolean | null;
    }
  | { kind: 'error'; text: string }
  | { kind: 'compaction'; retires: number; elagues: number }
  | { kind: 'controle' }
  | { kind: 'continuation'; message: string; tours: number };

/** Rend une nouvelle liste : jamais de mutation, pour que Svelte voie le changement. */
export function appliquer(items: ChatItem[], event: AgentEvent): ChatItem[] {
  switch (event.type) {
    case 'session':
      return items;

    case 'message_delta': {
      // Le modèle peut répondre en plusieurs morceaux : on les recolle dans la
      // même bulle plutôt que d'en empiler une par fragment.
      const dernier = items[items.length - 1];
      if (dernier?.kind === 'assistant') {
        return [
          ...items.slice(0, -1),
          { kind: 'assistant', text: dernier.text + event.payload.delta },
        ];
      }
      return [...items, { kind: 'assistant', text: event.payload.delta }];
    }

    case 'tool_call':
      return [
        ...items,
        {
          kind: 'tool',
          id: idLibre(items, event.payload.id ?? `${event.payload.name}-${items.length}`),
          name: event.payload.name,
          args: event.payload.arguments,
          result: null,
        },
      ];

    case 'tool_result': {
      const cible = trouverDernier(
        items,
        (item) =>
          item.kind === 'tool' &&
          item.result === null &&
          (event.payload.id === null || item.id === event.payload.id)
      );
      if (cible < 0) return items;
      const item = items[cible] as Extract<ChatItem, { kind: 'tool' }>;
      return remplacer(items, cible, { ...item, result: event.payload.result });
    }

    case 'approval_request':
      return [
        ...items,
        {
          kind: 'approval',
          requestId: event.payload.request_id,
          tool: event.payload.tool,
          args: event.payload.arguments,
          resume: event.payload.resume,
          expiresAt: event.payload.expires_at,
          approved: null,
        },
      ];

    case 'approval_resolved': {
      const cible = trouverDernier(
        items,
        (item) => item.kind === 'approval' && item.requestId === event.payload.request_id
      );
      if (cible < 0) return items;
      const item = items[cible] as Extract<ChatItem, { kind: 'approval' }>;
      return remplacer(items, cible, { ...item, approved: event.payload.approved });
    }

    case 'contexte_compacte': {
      // Une seule marque par tour : le rejeu après refus du fournisseur peut
      // rejouer l'événement, deux séparateurs collés ne diraient rien de plus.
      const marque = {
        kind: 'compaction',
        retires: event.payload.messages_retires,
        elagues: event.payload.resultats_elagues ?? 0,
      } as const;
      const dernier = items[items.length - 1];
      if (dernier?.kind === 'compaction') {
        return [...items.slice(0, -1), marque];
      }
      return [...items, marque];
    }

    case 'controle_relance':
      // La marque se pose après l'annonce fautive, donc le prochain
      // `message_delta` ouvre une bulle neuve au lieu de se recoller à elle.
      return [...items, { kind: 'controle' }];

    case 'discovery_active':
      return items;

    case 'gratuit_actif':
      // La bannière est gérée par ChatPanel (etat decouverte/banniereMode) ;
      // ici on ne modifie pas le fil de conversation.
      return items;

    case 'error':
      return cloturerSansReponse([...items, { kind: 'error', text: event.payload.message }]);

    case 'continuation':
      return [
        ...cloturerSansReponse(items),
        { kind: 'continuation', message: event.payload.message, tours: event.payload.tours },
      ];

    case 'done':
      // Un appel resté sans résultat à la fin du flux est une anomalie : le
      // montrer comme un échec plutôt qu'un spinner « En cours… » éternel.
      return cloturerSansReponse(items);
  }
}

/** Rend un identifiant qu'aucune carte d'outil déjà posée ne porte.
 *
 * Un fournisseur peut rejouer le même identifiant d'appel dans un tour ; le
 * `{#each}` clavé de l'affichage, lui, lève sur le doublon et fait disparaître
 * toute la conversation.
 */
function idLibre(items: ChatItem[], base: string): string {
  const pris = new Set<string>();
  for (const item of items) {
    if (item.kind === 'tool') pris.add(item.id);
  }
  let candidat = base;
  for (let n = 2; pris.has(candidat); n += 1) candidat = `${base}#${n}`;
  return candidat;
}

function cloturerSansReponse(items: ChatItem[]): ChatItem[] {
  return items.map((item) =>
    item.kind === 'tool' && item.result === null
      ? { ...item, result: { error: 'Aucun résultat reçu : l’appel est resté sans réponse.' } }
      : item
  );
}

/** Rehydrate une session persistée. Les approbations ne sont pas rejouables.
 *
 * Chaque message `tool` répond à un `tool_call` précis (via `tool_call_id`) :
 * sans réappariement, l'appel resterait une carte « En cours… » orpheline et
 * le résultat apparaîtrait en doublon, sans arguments. Les vieilles lignes
 * sans identifiant retombent sur un appariement séquentiel par nom d'outil.
 */
export function depuisMessages(messages: AgentMessage[]): ChatItem[] {
  const items: ChatItem[] = [];
  const enAttente = new Map<string, number>();
  // Les cartes d'outil sont affichées dans un `{#each}` clavé : deux items du
  // même identifiant font lever `each_key_duplicate` à Svelte, et l'exception
  // emporte le rendu de toute la conversation, écran vide et sans message.
  // Le cas se produit dès qu'un message assistant porte plusieurs `tool_calls`
  // sans identifiant fourni par le fournisseur : tous retombaient sur
  // `message.id`. L'unicité est donc garantie ici, à la source.
  const pris = new Set<string>();
  const unique = (base: string): string => {
    let candidat = base;
    for (let n = 2; pris.has(candidat); n += 1) candidat = `${base}#${n}`;
    pris.add(candidat);
    return candidat;
  };
  for (const message of messages) {
    if (message.role === 'user') {
      items.push({ kind: 'user', text: message.content });
    } else if (message.role === 'tool') {
      const resultat = lireJson(message.content);
      let cible: number;
      if (message.tool_call_id && enAttente.has(message.tool_call_id)) {
        cible = enAttente.get(message.tool_call_id) as number;
        enAttente.delete(message.tool_call_id);
      } else {
        // Fallback legacy : premier appel du même outil encore sans réponse.
        cible = trouverDernier(
          items,
          (item) => item.kind === 'tool' && item.result === null && item.name === message.tool_name
        );
      }
      if (cible >= 0) {
        const item = items[cible] as Extract<ChatItem, { kind: 'tool' }>;
        items[cible] = { ...item, result: resultat };
      } else {
        items.push({
          kind: 'tool',
          id: unique(message.id),
          name: message.tool_name ?? 'outil',
          args: {},
          result: resultat,
        });
      }
    } else if (message.tool_calls?.length) {
      for (const [rang, appel] of message.tool_calls.entries()) {
        const fonction = (appel as { function?: { name?: string; arguments?: string } }).function;
        // La clé d'appariement reste celle du fournisseur : c'est elle que
        // porte le `tool_call_id` du résultat. Le rang la remplace quand elle
        // manque, pour que deux appels d'un même message restent distincts.
        const cle = String((appel as { id?: string }).id ?? `${message.id}-${rang}`);
        enAttente.set(cle, items.length);
        items.push({
          kind: 'tool',
          id: unique(cle),
          name: fonction?.name ?? 'outil',
          args: lireJson(fonction?.arguments ?? '{}') ?? {},
          result: null,
        });
      }
    } else if (message.content) {
      items.push({ kind: 'assistant', text: message.content });
    }
  }
  return cloturerSansReponse(items);
}

function lireJson(texte: string): Record<string, unknown> | null {
  try {
    const valeur = JSON.parse(texte);
    return valeur && typeof valeur === 'object' ? (valeur as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/** Le dernier tour est-il complet en base ?
 *
 * Le serveur termine le tour même quand le client se déconnecte : après une
 * coupure réseau, la réponse existe en base et il suffit de la relire. Encore
 * faut-il savoir si elle y est déjà. Le critère est un message assistant
 * porteur de texte après le dernier message utilisateur. Un message assistant
 * qui ne porte que des `tool_calls` ne clôt rien : le tour tourne encore.
 */
export function tourTermine(messages: AgentMessage[]): boolean {
  let dernierUtilisateur = -1;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === 'user') {
      dernierUtilisateur = i;
      break;
    }
  }
  if (dernierUtilisateur < 0) return false;
  return messages
    .slice(dernierUtilisateur + 1)
    .some((m) => m.role === 'assistant' && !!m.content?.trim() && !m.tool_calls?.length);
}

function trouverDernier(items: ChatItem[], predicat: (item: ChatItem) => boolean): number {
  for (let i = items.length - 1; i >= 0; i -= 1) {
    if (predicat(items[i])) return i;
  }
  return -1;
}

function remplacer(items: ChatItem[], index: number, item: ChatItem): ChatItem[] {
  const copie = [...items];
  copie[index] = item;
  return copie;
}
