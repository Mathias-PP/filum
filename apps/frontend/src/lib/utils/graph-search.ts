/**
 * Recherche textuelle dans le graphe de sources.
 *
 * Sur une fiche de 150 références, retrouver à l'œil nu celle qu'on a en tête
 * est impossible. La comparaison est délibérément permissive : on cherche avec
 * le mot qu'on a en mémoire, pas avec l'orthographe exacte ni avec le champ où
 * la donnée est rangée.
 */

/** Insensible à la casse et aux accents : « Ancelin » ≡ « ancelin » ≡ « ANCELIN ». */
export function normalizeForSearch(text: string): string {
  return text.toLocaleLowerCase('fr').normalize('NFD').replace(/[̀-ͯ]/g, '');
}

/**
 * Découpe une requête en termes normalisés, combinés en ET.
 *
 * « madigan 2023 » doit trouver la référence alors que le nom et l'année vivent
 * dans deux champs distincts et ne sont jamais adjacents dans le texte.
 */
export function searchTerms(query: string): string[] {
  return normalizeForSearch(query.trim())
    .split(/\s+/)
    .filter((t) => t.length > 0);
}

/** Assemble les champs d'une référence en un texte cherchable unique. */
export function buildHaystack(fields: (string | null | undefined)[]): string {
  return normalizeForSearch(fields.filter(Boolean).join(' '));
}

export function matchesAllTerms(haystack: string, terms: string[]): boolean {
  return terms.every((t) => haystack.includes(t));
}
