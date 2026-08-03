/**
 * Étiquetage des nœuds « fiche » dans les vues graphe.
 *
 * Un nœud fiche représente un contenu, et un contenu se nomme par ses auteurs.
 * Publier une fiche n'est pas signer le contenu qu'elle documente : afficher le
 * créateur Philum laisserait croire qu'il en est l'auteur, y compris quand il
 * revendique la fiche — revendiquer, c'est répondre de la bibliographie, pas
 * s'attribuer la paternité de ce qui est cité. Les auteurs réels sont donc
 * toujours préférés, le créateur ne servant que faute de mieux.
 */
export interface CardLabelInput {
  authors?: string | null;
  creatorName?: string | null;
  creatorSlug?: string | null;
}

export function cardNodeLabel(card: CardLabelInput): string {
  const authors = card.authors?.trim();
  if (authors) return authors;
  return card.creatorName?.trim() || card.creatorSlug?.trim() || '';
}
