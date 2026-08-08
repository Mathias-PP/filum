/**
 * Ce qu'on dit au lecteur d'une citation, et ce qu'on ne dit pas.
 *
 * Une citation affichée nue demande de croire sur parole. Philum relit chaque
 * extrait dans la source ; encore faut-il que le résultat parvienne à celui qui
 * en a besoin. Quatre verdicts, plus l'absence de verdict — et cette absence est
 * la plus importante des cinq : sans elle, une citation jamais vérifiée se lit
 * exactement comme une citation vérifiée.
 *
 * Deux règles tenues par les tests :
 *
 * 1. **« Introuvable » n'accuse personne, et « illisible » encore moins.** Une
 *    page qui ne rend plus de texte ne dit rien sur la citation, ni dans un sens
 *    ni dans l'autre ; l'énoncer comme un défaut de la citation ferait porter à
 *    l'auteur·ice ce qui relève du site.
 * 2. **Relu contre un texte fourni n'est pas relu contre la page publique.** Le
 *    premier n'engage que l'auteur·ice, le second est reproductible par
 *    quiconque. Les confondre reviendrait à surévaluer le plus faible des deux.
 */
import type { SourceExcerpt } from '$lib/api/types';

export type VerdictTon = 'verifie' | 'nuance' | 'inconnu' | 'absent';

export interface VerdictLu {
  /** Ce qui s'affiche à côté de la citation. */
  label: string;
  /** Ce que révèle le survol : la nuance qui ne tient pas dans le label. */
  detail: string;
  ton: VerdictTon;
}

function laDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
}

export function lireVerdict(extrait: SourceExcerpt): VerdictLu {
  const fourni = extrait.verified_text_source === 'provided';
  const date = laDate(extrait.verified_at);
  const le = date ? ` le ${date}` : '';
  const contre = fourni
    ? "Relecture faite contre un texte fourni par l'auteur·ice, la page ne rendant rien d'exploitable : elle n'engage que sa parole."
    : 'Relecture faite contre la page publique : quiconque peut la refaire.';

  switch (extrait.verified_status) {
    case 'found':
      return {
        label: fourni ? `Relu sur un texte fourni${le}` : `Relu dans la source${le}`,
        detail: `Le passage a été retrouvé mot pour mot. ${contre}`,
        ton: fourni ? 'nuance' : 'verifie',
      };
    case 'moved':
      return {
        label: `Retrouvé, reformulé depuis${le}`,
        detail: `Le passage existe toujours mais ses mots ont changé depuis la citation. ${contre}`,
        ton: 'nuance',
      };
    case 'missing':
      return {
        label: `Introuvable dans la source${le}`,
        detail: `La relecture n'a pas retrouvé ce passage. La source a pu être remaniée. ${contre}`,
        ton: 'absent',
      };
    case 'unreadable':
      return {
        label: `Source illisible${le}`,
        detail:
          "La page ne rend aucun texte exploitable : la relecture ne dit rien sur cette citation, ni dans un sens ni dans l'autre.",
        ton: 'inconnu',
      };
    default:
      return {
        label: 'Jamais relu',
        detail:
          "Cette citation n'a pas encore été confrontée à la source. Elle est déclarée, pas vérifiée.",
        ton: 'inconnu',
      };
  }
}

/**
 * Les tons empruntent aux jetons de thème, pas à des nuances figées : un texte
 * posé sur une surface qui bascule doit basculer avec elle (cf. #338).
 */
export const CLASSES_VERDICT: Record<VerdictTon, string> = {
  verifie: 'text-emerald-700 dark:text-emerald-400',
  nuance: 'text-amber-700 dark:text-amber-400',
  absent: 'text-ink-tertiary italic',
  inconnu: 'text-ink-tertiary italic',
};
