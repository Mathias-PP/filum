/**
 * Bornage du nombre de références affichées d'un coup dans le graphe.
 *
 * Sur une fiche de 152 références, tout afficher d'emblée ne montre rien :
 * les nœuds se touchent, les étiquettes se recouvrent, et le lecteur doit
 * zoomer avant de comprendre ce qu'il regarde. Le graphe s'ouvre donc sur une
 * portion lisible, et dit combien il en garde en réserve.
 *
 * L'ordre retenu est celui de la fiche, pas un classement maison : choisir
 * « les plus importantes » supposerait un jugement que Philum n'a pas à
 * porter sur la bibliographie de quelqu'un d'autre.
 */

export const GRAPH_SOURCE_CAP = 60;

interface Capable {
  id: string;
  parent_source_id: string | null;
}

export interface CapResult<T> {
  kept: T[];
  hiddenCount: number;
}

/**
 * Garde les `cap` premières références dans l'ordre reçu, plus les parents
 * dont elles dépendent.
 *
 * Sans cette remontée, une source secondaire retenue verrait son parent
 * coupé et flotterait détachée : le graphe montrerait une filiation qui n'a
 * plus d'origine visible, ce qui est pire que de ne rien montrer.
 */
export function capSources<T extends Capable>(sources: T[], cap: number): CapResult<T> {
  if (cap <= 0 || sources.length <= cap) {
    return { kept: sources, hiddenCount: 0 };
  }

  const byId = new Map<string, T>(sources.map((s) => [s.id, s]));
  const keptIds = new Set<string>();

  for (const s of sources.slice(0, cap)) keptIds.add(s.id);

  for (const s of sources.slice(0, cap)) {
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

  // On repart de `sources` pour préserver l'ordre d'origine.
  const kept = sources.filter((s) => keptIds.has(s.id));
  return { kept, hiddenCount: sources.length - kept.length };
}
