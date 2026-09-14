/**
 * Lecture d'une synthèse ancrée : chaque phrase porte ses renvois
 * `[extrait:<id>]` vers les extraits verbatim de la fiche.
 *
 * Le serveur a déjà vérifié que chaque renvoi désigne un extrait de la fiche.
 * Ici on ne fait que rendre les renvois lisibles : un numéro par extrait, dans
 * l'ordre de première apparition, comme une note.
 */

export interface MorceauSynthese {
  texte: string;
  /** Numéros de note des extraits cités à la fin de ce morceau. */
  notes: number[];
}

export interface SyntheseLue {
  paragraphes: MorceauSynthese[][];
  /** Identifiant d'extrait, dans l'ordre des numéros (index 0 = note 1). */
  extraits: string[];
}

const RENVOI = /\[extrait:([0-9a-fA-F-]{36})\]/g;

export function lireSynthese(texte: string | null | undefined): SyntheseLue | null {
  if (!texte || !texte.trim()) return null;
  const extraits: string[] = [];
  const numero = (id: string): number => {
    const rang = extraits.indexOf(id);
    if (rang >= 0) return rang + 1;
    extraits.push(id);
    return extraits.length;
  };

  const paragraphes = texte
    .split(/\n\s*\n/)
    .map((bloc) => bloc.trim())
    .filter(Boolean)
    .map((bloc) => {
      const morceaux: MorceauSynthese[] = [];
      let debut = 0;
      let courant: MorceauSynthese | null = null;
      for (const m of bloc.matchAll(RENVOI)) {
        const avant = bloc.slice(debut, m.index).trim();
        if (avant || !courant) {
          courant = { texte: avant, notes: [] };
          morceaux.push(courant);
        }
        const n = numero(m[1].toLowerCase());
        if (!courant.notes.includes(n)) courant.notes.push(n);
        debut = (m.index ?? 0) + m[0].length;
      }
      const reste = bloc.slice(debut).trim();
      if (reste) morceaux.push({ texte: reste, notes: [] });
      return morceaux;
    });

  return { paragraphes, extraits };
}
