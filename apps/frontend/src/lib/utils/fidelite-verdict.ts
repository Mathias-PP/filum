/**
 * Le second verdict, et pourquoi il ne se confond pas avec le premier.
 *
 * `excerpt-verdict.ts` répond à « ces mots sont-ils dans la page ». Celui-ci
 * répond à autre chose : « la source dit-elle ce que l'annotation lui fait
 * dire ». Un passage peut être retrouvé au mot près et servir à étayer le
 * contraire de ce qu'il affirme ; les deux relectures sont donc indépendantes,
 * et rien ici ne doit laisser croire que l'une vaut l'autre.
 *
 * Trois règles tenues par les tests :
 *
 * 1. **Rien de tout ceci ne s'affiche publiquement.** Un verdict est un doute
 *    de travail, pas une information à publier : le rendre lisible du monde
 *    transformerait un garde-fou interne en accusation portée sur la source.
 *    L'API ne le sert que sur une route authentifiée, et ce module n'est appelé
 *    que depuis l'espace d'édition.
 * 2. **Aucun score, nulle part.** Pas de pourcentage, pas de note, pas de
 *    moyenne. Un scalaire invite à l'agrégation, et une moyenne de jugements
 *    catégoriels ne veut rien dire.
 * 3. **L'absence de verdict s'affiche.** « Jamais jugé » est un état, pas un
 *    vide à combler : sans lui, un extrait que le juge n'a jamais lu se lirait
 *    comme un extrait qu'il a validé.
 */

export type FideliteTon = 'accord' | 'desaccord' | 'inconnu';

export interface FideliteVerdict {
  excerpt_id: string;
  source_id: string;
  verdict: string | null;
  scope: string | null;
  checked_at: string | null;
  note: string | null;
}

export interface FideliteRapport {
  /** Le créateur a-t-il laissé le juge allumé. */
  actif: boolean;
  /** Sans clé, le juge ne tourne pas, quoi que dise `actif`. Les deux états se
   * distinguent : éteint volontairement n'est pas allumé sans moyen de tourner. */
  cle_configuree: boolean;
  /** Citations qu'un modèle a touchées et que le juge n'a jamais relues. */
  en_attente: number;
  verdicts: FideliteVerdict[];
  avertissement: string;
}

export interface FideliteLue {
  label: string;
  detail: string;
  ton: FideliteTon;
}

/** Indexe le rapport par citation, la forme dont l'affichage a besoin. */
export function parExtrait(rapport: FideliteRapport): Record<string, FideliteVerdict> {
  const index: Record<string, FideliteVerdict> = {};
  for (const v of rapport.verdicts) index[v.excerpt_id] = v;
  return index;
}

/** Sur quoi le juge s'est prononcé. Un verdict rendu sur un titre n'engage pas
 * ce qu'un verdict rendu sur l'article engage, et ne pas le dire serait mentir
 * par omission. */
const PORTEES: Record<string, string> = {
  texte_integral: 'Jugé sur le texte intégral de la source.',
  resume_seul: "Jugé sur un extrait du texte seulement, pas sur l'article entier.",
  metadonnees_seules: 'Jugé sans le texte de la source : seules ses métadonnées étaient lisibles.',
};

const VERDICTS: Record<string, FideliteLue> = {
  soutient: {
    label: 'La source soutient cette annotation',
    detail: "Le passage dit bien ce que l'annotation lui fait dire.",
    ton: 'accord',
  },
  contredit: {
    label: 'La source contredit cette annotation',
    detail: "Le passage affirme le contraire de ce que l'annotation lui fait dire.",
    ton: 'desaccord',
  },
  mixte: {
    label: 'La source nuance cette annotation',
    detail: "Le passage appuie une partie de l'annotation et en contredit une autre.",
    ton: 'desaccord',
  },
  ne_traite_pas: {
    label: 'La source ne traite pas ce sujet',
    detail: "Le passage parle d'autre chose que ce que l'annotation lui fait dire.",
    ton: 'desaccord',
  },
  preuve_insuffisante: {
    label: 'Pas de quoi trancher',
    detail:
      "Le texte disponible ne permet ni de confirmer ni d'infirmer l'annotation. Ce n'est pas un reproche fait à la citation.",
    ton: 'inconnu',
  },
  ambigu: {
    label: 'Le passage se lit dans les deux sens',
    detail: "Le texte supporte l'annotation comme son contraire, sans trancher.",
    ton: 'inconnu',
  },
};

const JAMAIS_JUGE: FideliteLue = {
  label: 'Jamais relu par le juge',
  detail:
    "Un modèle a écrit l'intitulé ou la mise en situation de cette citation, et personne ne les a confrontés à la source depuis.",
  ton: 'inconnu',
};

export function lireFidelite(v: FideliteVerdict): FideliteLue {
  if (!v.verdict) return JAMAIS_JUGE;
  const lu = VERDICTS[v.verdict];
  // Une valeur inconnue ne se rapproche pas de la plus proche : « plutôt
  // favorable » n'est pas « soutient ». Elle s'affiche pour ce qu'elle est.
  if (!lu) {
    return {
      label: 'Verdict non reconnu',
      detail: `Le juge a rendu « ${v.verdict} », qui ne fait pas partie du vocabulaire attendu.`,
      ton: 'inconnu',
    };
  }
  const portee = v.scope ? PORTEES[v.scope] : undefined;
  const note = (v.note || '').trim();
  return {
    ...lu,
    detail: [lu.detail, portee, note].filter(Boolean).join(' '),
  };
}

export const CLASSES_FIDELITE: Record<FideliteTon, string> = {
  accord: 'text-emerald-700 dark:text-emerald-400',
  desaccord: 'text-amber-700 dark:text-amber-400',
  inconnu: 'text-ink-tertiary italic',
};

/** La mention que le juge porte tant qu'il n'a pas été mesuré. Elle s'affiche
 * en clair : livrer sans mesure est acceptable, promettre sans mesure ne l'est
 * pas. */
export const AVERTISSEMENT_NON_MESURE =
  "Ce juge n'a jamais été mesuré contre un corpus corrigé. Son verdict est une indication à vérifier, pas une preuve.";
