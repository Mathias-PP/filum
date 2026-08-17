/**
 * Étiquetage des nœuds « fiche » dans les vues graphe.
 *
 * Un nœud fiche représente un contenu ; un contenu se nomme par ses auteurs.
 * Publier une fiche n'est pas signer le contenu qu'elle documente : afficher
 * le créateur Philum laisserait croire qu'il en est l'auteur, y compris quand
 * il revendique la fiche (revendiquer, c'est répondre de la bibliographie,
 * pas s'attribuer la paternité de ce qui est cité).
 *
 * Contrat : **on ne retombe jamais sur le créateur.** Faute d'auteurs
 * déclarés, on retombe sur le titre du contenu — même règle que pour les
 * sources (`SourceGraph.authorLabel`). Si le titre manque aussi, chaîne vide.
 * Mieux vaut un nœud sans étiquette qu'un nœud qui ment sur l'auteur.
 *
 * Régression historique : ce fichier a plusieurs fois été « corrigé » vers un
 * fallback créateur (test explicite le codifiant), puis re-corrigé. Le
 * fallback n'a jamais été acceptable — même règle qu'ADR-019 et #448 pour la
 * meta `citation_author`. Verrouillé par tests, ne pas revenir en arrière.
 */
export interface CardLabelInput {
  authors?: string | null;
  title?: string | null;
}

export function cardNodeLabel(card: CardLabelInput): string {
  const authors = card.authors?.trim();
  if (authors) return authors;
  return card.title?.trim() ?? '';
}
