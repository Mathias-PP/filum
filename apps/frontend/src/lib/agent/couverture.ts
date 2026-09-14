import type { CouvertureFiche } from '$lib/api/agent';

/**
 * La phrase qui résume la couverture d'une fiche par son plan, ou null sans plan.
 *
 * Un compte, pas un score : combien de sous-questions portent au moins un
 * extrait, sur combien le plan en pose.
 */
export function resumeCouverture(couverture: CouvertureFiche | null): string | null {
  const total = couverture?.sous_questions.length ?? 0;
  if (!couverture || total === 0) return null;
  const couvertes = couverture.sous_questions.filter((q) => q.extraits > 0).length;
  const sujet = total > 1 ? 'sous-questions' : 'sous-question';
  if (couvertes === total) {
    return total > 1
      ? `Les ${total} ${sujet} du plan ont au moins un extrait`
      : 'La sous-question du plan a au moins un extrait';
  }
  return `${couvertes} ${sujet} sur ${total} avec au moins un extrait`;
}

export function libelleExtraits(nombre: number): string {
  if (nombre === 0) return 'aucun extrait';
  return `${nombre} extrait${nombre > 1 ? 's' : ''}`;
}
