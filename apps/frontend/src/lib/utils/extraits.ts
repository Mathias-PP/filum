/**
 * Libellé du badge qui signale, sur une ligne de source repliée, qu'elle porte
 * des passages cités mot pour mot.
 *
 * Les extraits ne s'affichent qu'une fois la source dépliée. Sur une fiche de
 * cinquante références dont quatorze seulement sont citées, rien ne distinguait
 * les unes des autres : il fallait ouvrir chaque ligne pour savoir laquelle
 * portait une citation vérifiable.
 */
export function libelleExtraits(nombre: number | null | undefined): string | null {
  if (!nombre || nombre <= 0) return null;
  return `${nombre} extrait${nombre > 1 ? 's' : ''}`;
}
