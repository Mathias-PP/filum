/**
 * Analyseur markdown minimal pour les bulles de l'agent.
 *
 * L'agent répond en markdown (titres, listes, gras, liens, extraits de code)
 * mais la bulle ne doit JAMAIS injecter de HTML brut : le texte vient d'un
 * modèle, pas d'un auteur de confiance. Ce module rend donc des structures
 * typées que le composant Svelte transforme en éléments réels — aucun
 * `{@html}`, donc aucune surface XSS. Le sous-ensemble couvert est celui que
 * les modèles produisent en pratique dans un chat ; tout le reste reste du
 * texte lisible.
 */

export type Segment =
  | { t: 'texte'; texte: string }
  | { t: 'code'; code: string }
  | { t: 'gras'; texte: string }
  | { t: 'italique'; texte: string }
  | { t: 'lien'; texte: string; href: string };

export type Bloc =
  | { t: 'titre'; niveau: number; segments: Segment[] }
  | { t: 'paragraphe'; segments: Segment[] }
  | { t: 'liste'; ordonnee: boolean; items: Segment[][] }
  | { t: 'citation'; segments: Segment[] }
  | { t: 'code'; texte: string }
  | { t: 'tableau'; entetes: Segment[][]; lignes: Segment[][][] }
  | { t: 'separateur' };

/** Ligne de séparation d'un tableau : `|---|:---:|`, bordures facultatives. */
const RE_SEPARATEUR_TABLEAU = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

function cellules(ligne: string): string[] {
  let t = ligne.trim();
  if (t.startsWith('|')) t = t.slice(1);
  if (t.endsWith('|')) t = t.slice(0, -1);
  return t.split('|').map((c) => c.trim());
}

/** Liens http(s) et mailto uniquement : un `javascript:` dans une réponse de
 * modèle ne doit jamais devenir cliquable. */
function securiserUrl(href: string): string | null {
  return /^https?:\/\//i.test(href) || href.startsWith('mailto:') ? href : null;
}

/** Le lien n'est reconnu qu'aux schémas sûrs : un `javascript:` ne doit jamais
 * être tokenisé comme lien, il restera du texte ordinaire. */
const MOTIF_INLINE =
  /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\*[^*\n]+\*)|(\[[^\]\n]+\]\((?:https?:\/\/|mailto:)[^)\s]+\))/g;

export function segmentsInline(texte: string): Segment[] {
  const segments: Segment[] = [];
  let dernier = 0;
  for (const m of texte.matchAll(MOTIF_INLINE)) {
    const brut = m[0];
    if (m.index > dernier) {
      segments.push({ t: 'texte', texte: texte.slice(dernier, m.index) });
    }
    if (brut.startsWith('`')) {
      segments.push({ t: 'code', code: brut.slice(1, -1) });
    } else if (brut.startsWith('**')) {
      segments.push({ t: 'gras', texte: brut.slice(2, -2) });
    } else if (brut.startsWith('*')) {
      segments.push({ t: 'italique', texte: brut.slice(1, -1) });
    } else {
      const lien = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(brut);
      const href = lien ? securiserUrl(lien[2]) : null;
      if (lien && href) {
        segments.push({ t: 'lien', texte: lien[1], href });
      } else {
        // Lien à schéma interdit ou syntaxe à moitié formée : texte brut.
        segments.push({ t: 'texte', texte: brut });
      }
    }
    dernier = m.index + brut.length;
  }
  if (dernier < texte.length) {
    segments.push({ t: 'texte', texte: texte.slice(dernier) });
  }
  return segments.length > 0 ? segments : [{ t: 'texte', texte }];
}

const RE_TITRE = /^(#{1,6})\s+(.*)$/;
const RE_SEPARATEUR = /^(-{3,}|\*{3,}|_{3,})$/;
const RE_ITEM_PUCE = /^\s*[-*+]\s+(.*)$/;
const RE_ITEM_NUMERO = /^\s*(\d+)[.)]\s+(.*)$/;
const RE_CITATION = /^>\s?(.*)$/;

export function analyser(texte: string): Bloc[] {
  const lignes = texte.replace(/\r\n/g, '\n').split('\n');
  const blocs: Bloc[] = [];
  let paragraphe: string[] = [];

  const viderParagraphe = () => {
    if (paragraphe.length > 0) {
      blocs.push({ t: 'paragraphe', segments: segmentsInline(paragraphe.join(' ')) });
      paragraphe = [];
    }
  };

  for (let i = 0; i < lignes.length; i += 1) {
    const ligne = lignes[i];
    const t = ligne.trim();

    if (t === '') {
      viderParagraphe();
      continue;
    }

    // Bloc de code clôturé : rendu verbatim, sans analyse inline.
    if (t.startsWith('```')) {
      viderParagraphe();
      const contenu: string[] = [];
      i += 1;
      while (i < lignes.length && !lignes[i].trim().startsWith('```')) {
        contenu.push(lignes[i]);
        i += 1;
      }
      blocs.push({ t: 'code', texte: contenu.join('\n') });
      continue;
    }

    const titre = RE_TITRE.exec(t);
    if (titre) {
      viderParagraphe();
      blocs.push({
        t: 'titre',
        niveau: Math.min(titre[1].length, 3),
        segments: segmentsInline(titre[2]),
      });
      continue;
    }

    // Tableau : une ligne à barres verticales suivie d'une ligne de tirets.
    // Sans cette règle, un tableau de l'agent s'affichait en barres brutes.
    if (t.includes('|') && i + 1 < lignes.length && RE_SEPARATEUR_TABLEAU.test(lignes[i + 1])) {
      viderParagraphe();
      const entetes = cellules(t);
      const lignesTableau: Segment[][][] = [];
      i += 2;
      while (i < lignes.length && lignes[i].trim() !== '' && lignes[i].includes('|')) {
        // Une ligne plus courte ou plus longue que l'en-tête est ramenée à sa
        // largeur : le tableau reste rectangulaire.
        const brutes = cellules(lignes[i]);
        lignesTableau.push(entetes.map((_, k) => segmentsInline(brutes[k] ?? '')));
        i += 1;
      }
      i -= 1; // la boucle externe réincrémentera
      blocs.push({
        t: 'tableau',
        entetes: entetes.map((e) => segmentsInline(e)),
        lignes: lignesTableau,
      });
      continue;
    }

    if (RE_SEPARATEUR.exec(t)) {
      viderParagraphe();
      blocs.push({ t: 'separateur' });
      continue;
    }

    const citation = RE_CITATION.exec(ligne);
    if (citation) {
      viderParagraphe();
      const morceaux = [citation[1]];
      while (i + 1 < lignes.length) {
        const suivante = RE_CITATION.exec(lignes[i + 1]);
        if (!suivante) break;
        morceaux.push(suivante[1]);
        i += 1;
      }
      blocs.push({ t: 'citation', segments: segmentsInline(morceaux.join(' ')) });
      continue;
    }

    const puce = RE_ITEM_PUCE.exec(ligne);
    const numero = RE_ITEM_NUMERO.exec(ligne);
    if (puce || numero) {
      viderParagraphe();
      const ordonnee = Boolean(numero);
      const items: Segment[][] = [];
      while (i < lignes.length) {
        const p = RE_ITEM_PUCE.exec(lignes[i]);
        const n = RE_ITEM_NUMERO.exec(lignes[i]);
        if (ordonnee && n) items.push(segmentsInline(n[2]));
        else if (!ordonnee && p) items.push(segmentsInline(p[1]));
        else break;
        i += 1;
      }
      i -= 1; // la boucle externe réincrémentera
      blocs.push({ t: 'liste', ordonnee, items });
      continue;
    }

    paragraphe.push(t);
  }
  viderParagraphe();
  return blocs;
}
