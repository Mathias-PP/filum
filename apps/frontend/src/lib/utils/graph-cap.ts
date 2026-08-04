/**
 * Bornage du nombre de références affichées d'un coup dans le graphe.
 *
 * Sur une fiche de 152 références, tout afficher d'emblée ne montre rien :
 * les nœuds se touchent, les étiquettes se recouvrent, et le lecteur doit
 * zoomer avant de comprendre ce qu'il regarde. Le graphe s'ouvre donc sur une
 * portion lisible, et dit combien il en garde en réserve.
 *
 * Le seul classement admis est celui que la créatrice ou le créateur a
 * lui-même déclaré : les sources marquées « clé » passent devant. Pour tout le
 * reste, l'ordre est celui de la fiche — décider laquelle des références de
 * quelqu'un d'autre « compte » supposerait un jugement que Philum n'a pas à
 * porter.
 */

/** Plafond par défaut. L'utilisateur peut le relever ou l'abaisser lui-même. */
export const GRAPH_SOURCE_CAP = 250;

/**
 * Seuil au-delà duquel le graphe prévient que l'affichage devient dense.
 *
 * C'est un avertissement, pas une borne : le plafond saisi n'est jamais
 * refusé. Une fiche peut légitimement compter 800 références, et interdire de
 * les demander cacherait un travail réel derrière un confort de lecture.
 */
export const GRAPH_CAP_COMFORT = 500;

interface Capable {
  id: string;
  parent_source_id: string | null;
  is_pivot?: boolean;
}

export interface CapResult<T> {
  kept: T[];
  hiddenCount: number;
}

/**
 * Garde `cap` références — les sources clés d'abord, puis l'ordre de la fiche —
 * plus les parents dont elles dépendent.
 *
 * Sans cette remontée, une source secondaire retenue verrait son parent
 * coupé et flotterait détachée : le graphe montrerait une filiation qui n'a
 * plus d'origine visible, ce qui est pire que de ne rien montrer.
 */
export function capSources<T extends Capable>(sources: T[], cap: number): CapResult<T> {
  if (cap <= 0 || sources.length <= cap) {
    return { kept: sources, hiddenCount: 0 };
  }

  // Tri stable : les clés remontent, l'ordre de la fiche est conservé au sein
  // de chaque groupe.
  const ranked = sources
    .map((s, i) => ({ s, i }))
    .sort((a, b) => Number(b.s.is_pivot ?? false) - Number(a.s.is_pivot ?? false) || a.i - b.i)
    .map(({ s }) => s);

  const kept = withAncestors(sources, ranked.slice(0, cap));
  return { kept, hiddenCount: sources.length - kept.length };
}

/**
 * Complète une sélection par les parents dont elle dépend, en conservant
 * l'ordre d'origine.
 *
 * Sans cette remontée, une source secondaire retenue verrait son parent coupé
 * et flotterait détachée : le graphe montrerait une filiation qui n'a plus
 * d'origine visible, ce qui est pire que de ne rien montrer.
 */
function withAncestors<T extends Capable>(sources: T[], selected: T[]): T[] {
  const byId = new Map<string, T>(sources.map((s) => [s.id, s]));
  const keptIds = new Set<string>(selected.map((s) => s.id));

  for (const s of selected) {
    let parentId = s.parent_source_id;
    // Garde-fou : un cycle de filiation, même invalide, ne doit pas figer le
    // rendu de la page.
    const seen = new Set<string>([s.id]);
    while (parentId && !seen.has(parentId)) {
      seen.add(parentId);
      const parent = byId.get(parentId);
      if (!parent) break;
      keptIds.add(parent.id);
      parentId = parent.parent_source_id;
    }
  }

  return sources.filter((s) => keptIds.has(s.id));
}

/**
 * Ne garde que les sources déclarées « clé », et ce dont elles descendent.
 *
 * Le filtre s'appuie sur la seule marque que la créatrice ou le créateur a
 * posée : rien n'est deviné. Une liste sans aucune marque est rendue telle
 * quelle — filtrer sur un critère absent viderait le graphe au lieu de le
 * resserrer.
 */
export function keySourcesOnly<T extends Capable>(sources: T[]): T[] {
  const pivots = sources.filter((s) => s.is_pivot);
  if (pivots.length === 0) return sources;
  return withAncestors(sources, pivots);
}
