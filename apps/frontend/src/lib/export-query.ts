/** L'adresse d'un export à la carte, construite depuis ce que l'utilisateur a coché.
 *
 * Séparé du composant parce que c'est la seule partie qui peut se tromper
 * silencieusement : une virgule oubliée, un degré mal numéroté, et le fichier
 * téléchargé n'est pas celui qu'on a demandé — sans rien qui le signale.
 *
 * La grammaire est celle du backend (`app/services/export_scope.py` et
 * `export_neighbourhood.py`). Deux règles s'y jouent :
 *
 * - `include` absent veut dire « tout », `include=` vide veut dire « les
 *   références seules ». Le panneau écrit donc toujours le paramètre, même
 *   quand il est vide : sinon décocher les quatre cases ne ferait rien.
 * - Un sens de voisinage sans degré n'écrit rien du tout. Un `cited=` vide
 *   serait un degré illisible côté serveur, pas une absence.
 */

export const SECTIONS = [
  { key: 'annotations', label: 'Notes du créateur' },
  { key: 'excerpts', label: 'Extraits cités' },
  { key: 'archives', label: 'Archives' },
  { key: 'reliability', label: 'Rétractations, accès ouvert' },
] as const;

export type SectionKey = (typeof SECTIONS)[number]['key'];
export type Scope = Record<SectionKey, boolean>;

export const MAX_DEGREE = 3;

export function fullScope(): Scope {
  return { annotations: true, excerpts: true, archives: true, reliability: true };
}

export function emptyScope(): Scope {
  return { annotations: false, excerpts: false, archives: false, reliability: false };
}

/** Les formats sur lesquels le périmètre mord.
 *
 * BibTeX, RIS, CSL et les styles de citation obéissent à des conventions
 * fermées : y glisser un extrait produirait un fichier qu'un gestionnaire de
 * références refuserait. Le panneau grise leurs cases plutôt que de laisser
 * croire à un choix qui n'aura aucun effet. */
export const SCOPED_FORMATS = new Set(['json', 'philum', 'markdown', 'docx']);

/** Les formats qui savent porter des fiches voisines. Le Word en est exclu :
 * un document imprimable a une fin, un voisinage n'en a pas. */
export const NEIGHBOUR_FORMATS = new Set(['json', 'philum', 'markdown']);

export function serialiseScope(scope: Scope): string {
  return SECTIONS.filter(({ key }) => scope[key])
    .map(({ key }) => key)
    .join(',');
}

/** `[{...}, {...}]` -> `« 1:excerpts|2: »`. Index 0 = degré 1. */
export function serialiseDegrees(degrees: Scope[]): string {
  return degrees.map((scope, i) => `${i + 1}:${serialiseScope(scope)}`).join('|');
}

export interface ExportRequest {
  format: string;
  scope: Scope;
  /** Les fiches que celle-ci cite — un périmètre par degré, dans l'ordre. */
  cited: Scope[];
  /** Les fiches qui citent celle-ci. */
  citing: Scope[];
}

export function buildExportUrl(base: string, req: ExportRequest): string {
  const params = new URLSearchParams({ format: req.format });
  if (SCOPED_FORMATS.has(req.format)) {
    params.set('include', serialiseScope(req.scope));
  }
  if (NEIGHBOUR_FORMATS.has(req.format)) {
    if (req.cited.length) params.set('cited', serialiseDegrees(req.cited));
    if (req.citing.length) params.set('citing', serialiseDegrees(req.citing));
  }
  return `${base}?${params}`;
}
