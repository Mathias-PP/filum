/**
 * Libellé du bandeau de légende du graphe.
 *
 * Extrait du composant pour être testable seul : le texte a déjà changé
 * trois fois, et une régression de pluriel ou de ponctuation passe
 * inaperçue dans un composant de 2 400 lignes.
 */
export function legendLabel(count: number): string {
  const plural = count > 1;
  const fiches = plural ? 'fiches Philum reliées' : 'fiche Philum reliée';
  return `${count} ${fiches}. Cliquez la pastille « + » pour déplier ses sources, le nœud pour voir sa référence.`;
}
