/**
 * Rapport déclaré entre le propos d'un contenu et ce que dit une source.
 *
 * Une bibliographie dit sur quoi on s'appuie, jamais comment. Le lecteur qui
 * voit trente sources ne peut pas distinguer celle qui confirme le propos de
 * celle qui le contredit et que l'auteur cite honnêtement.
 *
 * **Déclaratif, jamais inféré.** C'est l'auteur de la fiche qui l'affirme et
 * en répond. `null` (non déclaré) reste la valeur normale et ne vaut pas
 * « mentionne » : l'un est un silence, l'autre une réponse.
 */

import type { SourceStance } from '$lib/api/types';

export interface StanceStyle {
  label: string;
  /** Ce que l'auteur affirme en choisissant cette valeur. */
  help: string;
  /** Couleur du trait dans le graphe. */
  stroke: string;
  bgClass: string;
}

export const STANCE_STYLES: Record<SourceStance, StanceStyle> = {
  appuie: {
    label: 'Appuie',
    help: 'La source soutient ce qui est affirmé.',
    stroke: '#639922',
    bgClass: 'bg-emerald-100 text-emerald-800',
  },
  'nuance-contredit': {
    label: 'Nuance ou contredit',
    help: 'La source limite la portée du propos, ou le contredit.',
    stroke: '#D64545',
    bgClass: 'bg-rose-100 text-rose-800',
  },
  mentionne: {
    label: 'Mentionne',
    help: 'La source est citée sans que le propos en dépende.',
    stroke: '#8B8B8B',
    bgClass: 'bg-neutral-100 text-neutral-700',
  },
  contexte: {
    label: 'Contexte',
    help: 'La source apporte un cadre, une méthode ou un historique.',
    stroke: '#378ADD',
    bgClass: 'bg-blue-100 text-blue-800',
  },
};

/** Ordre d'affichage dans le sélecteur et la légende. */
export const STANCE_ORDER: SourceStance[] = ['appuie', 'nuance-contredit', 'contexte', 'mentionne'];

/** Trait par défaut : le gris neutre du graphe, inchangé depuis toujours. */
export const STANCE_STROKE_UNDECLARED = '#CBD5E1';

/**
 * Couleur du trait pour une arête.
 *
 * Une valeur inconnue (backend en avance sur le frontend, donnée saisie hors
 * UI) retombe sur le neutre plutôt que de faire planter le rendu.
 */
export function stanceStroke(stance: string | null | undefined): string {
  if (!stance) return STANCE_STROKE_UNDECLARED;
  return STANCE_STYLES[stance as SourceStance]?.stroke ?? STANCE_STROKE_UNDECLARED;
}

export function stanceStyle(stance: string | null | undefined): StanceStyle | null {
  if (!stance) return null;
  return STANCE_STYLES[stance as SourceStance] ?? null;
}
