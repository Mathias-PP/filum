/**
 * Ce qui a changé entre deux lectures de la fiche en direct, et où regarder.
 *
 * Le panneau relit la fiche après chaque action de l'agent. Sans comparaison,
 * un extrait ajouté au bas d'une fiche de quinze sources passait inaperçu : il
 * fallait le chercher en faisant défiler. La comparaison dit ce qui vient de
 * changer (pour l'éclairer) et désigne une cible (pour y amener l'œil).
 *
 * Fonction pure, testée sans navigateur.
 */

import type { Source, SourceExcerpt } from '$lib/api/types';

export interface Cible {
  kind: 'extrait' | 'source';
  id: string;
}

export interface Ecart {
  /** Sources nouvelles, modifiées, ou qui portent un extrait nouveau ou modifié. */
  sources: Set<string>;
  /** Extraits nouveaux ou modifiés (texte, mise en situation, verdict). */
  extraits: Set<string>;
  /** Où amener l'œil, ou null quand rien n'a changé. */
  cible: Cible | null;
}

function signatureSource(s: Source): string {
  return JSON.stringify([
    s.title,
    s.stance,
    s.retraction_status,
    s.oa_status,
    s.archive_status,
    s.annotation,
  ]);
}

function signatureExtrait(e: SourceExcerpt): string {
  return JSON.stringify([e.text, e.context, e.verified_status]);
}

/**
 * Compare deux lectures. `avant` à null signifie un premier affichage ou un
 * changement de fiche : rien n'est « nouveau », rien ne s'éclaire.
 *
 * Priorité de la cible : le dernier extrait ajouté ou modifié, sinon la
 * dernière source ajoutée, sinon la dernière source modifiée. « Dernier » suit
 * l'ordre d'affichage, qui est celui dans lequel l'agent complète la fiche.
 */
export function comparerFiches(avant: Source[] | null, apres: Source[]): Ecart {
  const ecart: Ecart = { sources: new Set(), extraits: new Set(), cible: null };
  if (!avant) return ecart;

  const sourcesAvant = new Map(avant.map((s) => [s.id, signatureSource(s)]));
  const extraitsAvant = new Map<string, string>();
  for (const s of avant) for (const e of s.excerpts) extraitsAvant.set(e.id, signatureExtrait(e));

  let extraitCible: string | null = null;
  let sourceAjoutee: string | null = null;
  let sourceModifiee: string | null = null;

  for (const s of apres) {
    const precedente = sourcesAvant.get(s.id);
    if (precedente === undefined) {
      ecart.sources.add(s.id);
      sourceAjoutee = s.id;
    } else if (precedente !== signatureSource(s)) {
      ecart.sources.add(s.id);
      sourceModifiee = s.id;
    }
    for (const e of s.excerpts) {
      const signature = extraitsAvant.get(e.id);
      if (signature === undefined || signature !== signatureExtrait(e)) {
        ecart.extraits.add(e.id);
        ecart.sources.add(s.id);
        extraitCible = e.id;
      }
    }
  }

  if (extraitCible) ecart.cible = { kind: 'extrait', id: extraitCible };
  else if (sourceAjoutee) ecart.cible = { kind: 'source', id: sourceAjoutee };
  else if (sourceModifiee) ecart.cible = { kind: 'source', id: sourceModifiee };
  return ecart;
}
