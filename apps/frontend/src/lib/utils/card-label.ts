/**
 * Étiquetage des nœuds « fiche » dans les vues graphe.
 *
 * Une fiche non revendiquée (`is_seed`) documente le contenu d'un tiers :
 * l'étiqueter au nom de son créateur Philum laisse croire qu'il en est
 * l'auteur. On affiche donc les auteurs réels dès qu'on les connaît — le
 * backend les remonte depuis la source qui désigne la fiche — et on ne retombe
 * sur le créateur que faute de mieux.
 */
export interface CardLabelInput {
  authors?: string | null;
  creatorName?: string | null;
  creatorSlug?: string | null;
  isSeed?: boolean;
}

export function cardNodeLabel(card: CardLabelInput): string {
  const authors = card.authors?.trim();
  const creator = card.creatorName?.trim() || card.creatorSlug?.trim();
  if (card.isSeed && authors) return authors;
  return creator || authors || '';
}
