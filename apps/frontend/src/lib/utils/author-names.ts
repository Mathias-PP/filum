/**
 * Découpage d'une liste d'auteurs saisie ou importée en texte libre.
 *
 * Le graphe affiche par défaut le seul premier nom : sur une référence à
 * quinze auteurs, la liste complète recouvre les nœuds voisins et rend la
 * frise illisible. Mais tronquer une chaîne à la 22e lettre coupe au milieu
 * d'un nom ; il faut donc savoir où finit un auteur et où commence le suivant.
 *
 * Les imports viennent de partout — Crossref rend « Smith, J.; Doe, A. »,
 * un scraping HTML « John Smith, Jane Doe », une saisie manuelle « Smith J.,
 * Doe A. ». Aucun format n'est garanti. La règle est donc conservatrice : en
 * cas de doute, on préfère rendre la chaîne entière plutôt qu'un nom coupé en
 * deux, parce qu'un nom faux est pire qu'un nom long.
 */

/** Une virgule suivie de seules initiales continue le même auteur. */
const INITIALS = /^(?:[\p{Lu}]\.?[\s-]*){1,4}$/u;

/**
 * Les auteurs d'une chaîne libre, dans l'ordre. Tableau vide si la chaîne
 * ne contient rien d'exploitable.
 */
export function splitAuthors(authors: string | null | undefined): string[] {
  const raw = (authors ?? '').trim();
  if (!raw) return [];

  // Un point-virgule est un séparateur sans ambiguïté : quand il est là, il
  // tranche, et les virgules restantes appartiennent aux noms.
  if (raw.includes(';')) {
    return raw
      .split(';')
      .map((p) => p.trim())
      .filter(Boolean);
  }

  const parts = raw
    .split(/\s*(?:,|\bet\b|\band\b|&)\s*/i)
    .map((p) => p.trim())
    .filter(Boolean);

  // « Smith, J., Doe, A. » : recoller les initiales au nom qui précède, sans
  // quoi « J. » passerait pour un auteur à part entière.
  const merged: string[] = [];
  for (const part of parts) {
    if (merged.length > 0 && INITIALS.test(part)) {
      merged[merged.length - 1] = `${merged[merged.length - 1]}, ${part}`;
    } else {
      merged.push(part);
    }
  }
  return merged;
}

/**
 * Rendu de la liste selon ce que le lecteur a demandé à voir.
 *
 * Aucun des deux drapeaux : la chaîne d'origine, inchangée — ne rien réduire
 * reste une option, et c'est la seule qui ne perd aucune information.
 */
export function authorSummary(
  authors: string | null | undefined,
  opts: { first: boolean; last: boolean }
): string {
  const raw = (authors ?? '').trim();
  if (!raw) return '';
  if (!opts.first && !opts.last) return raw;

  const names = splitAuthors(raw);
  if (names.length <= 1) return raw;

  if (opts.first && opts.last) {
    if (names.length === 2) return `${names[0]}, ${names[names.length - 1]}`;
    // L'ellipse dit qu'il manque des auteurs entre les deux : sans elle, le
    // lecteur croirait la référence signée par deux personnes.
    return `${names[0]} … ${names[names.length - 1]}`;
  }
  const kept = opts.first ? names[0] : names[names.length - 1];
  // « et al. » signale que la liste est tronquée, pas que l'auteur est seul.
  return `${kept} et al.`;
}
