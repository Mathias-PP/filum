/**
 * La fiche sur laquelle l'agent travaille, lue dans le fil.
 *
 * Les outils désignent une fiche par son slug, dans leurs arguments
 * (`slug`, `card_slug`) ou dans leur résultat. La fiche courante est la
 * dernière ainsi nommée : c'est elle que le panneau de droite montre, et il la
 * relit à chaque action terminée.
 */

import type { ChatItem } from './conversation';

function texte(valeur: unknown): string | null {
  return typeof valeur === 'string' && valeur.trim() ? valeur : null;
}

export function slugFicheCourante(items: ChatItem[]): string | null {
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    if (item.kind !== 'tool') continue;
    // Un appel en échec ne désigne rien de fiable : son slug a pu être refusé.
    const resultat = item.result && !('error' in item.result) ? item.result : null;
    const imbriquee =
      resultat?.card && typeof resultat.card === 'object'
        ? texte((resultat.card as Record<string, unknown>).slug)
        : null;
    const slug =
      texte(resultat?.card_slug) ??
      texte(resultat?.slug) ??
      imbriquee ??
      (item.result && 'error' in item.result
        ? null
        : (texte(item.args.card_slug) ?? texte(item.args.slug)));
    if (slug) return slug;
  }
  return null;
}

/** Nombre d'appels terminés : chaque nouvelle action finie relit la fiche. */
export function appelsTermines(items: ChatItem[]): number {
  let n = 0;
  for (const item of items) if (item.kind === 'tool' && item.result !== null) n += 1;
  return n;
}
