/**
 * Disposition chronologique du graphe : une abscisse par année de publication.
 *
 * Le mode réseau montre qui dépend de qui ; il ne dit rien de l'ancienneté.
 * Or « cette affirmation s'appuie sur un article de 1998 » est une information
 * que le lecteur ne peut pas déduire d'un maillage. D'où un second axe de
 * lecture : le temps.
 *
 * Règle d'honnêteté, la même que partout ailleurs dans Philum : une source sans
 * date connue ne reçoit **jamais** une position inventée sur la frise. Elle est
 * garée dans une colonne à part, explicitement étiquetée « sans date ».
 * L'alternative — la coller à l'année médiane, ou à l'extrémité — ferait dire au
 * graphe une chose que personne n'a vérifiée.
 *
 * ⚠️ Un simple écart ne suffit pas. **Une position sur un axe temporel signifie
 * une date, quel que soit l'écart** : signalé à l'usage le 2026-08-04, la
 * colonne collée à gauche d'une frise 1935→2021 se lisait « années 1940-1960 ».
 * D'où `breakX` : la colonne est séparée de la frise par un **filet de rupture**
 * explicite, la convention usuelle pour dire « l'échelle s'interrompt ici ».
 * Sans ce filet, l'absence redevient une valeur — et une valeur fausse.
 *
 * La colonne est placée **après** la frise, à droite. À gauche, elle occupait la
 * place que l'œil lit comme « le plus ancien » ; à droite, après la fin de
 * l'échelle, elle se lit comme ce qu'elle est : hors frise.
 */

/** Largeur de la colonne « sans date », en unités de repère du graphe. */
export const UNDATED_BAND = 130;

/**
 * Écart entre la colonne « sans date » et la première année datée.
 *
 * Assez large pour loger le filet de rupture et ne pas se lire comme un simple
 * intervalle entre deux graduations.
 */
export const UNDATED_GUTTER = 170;

export interface ChronoItem {
  id: string;
  published_at: string | null;
}

export interface ChronoTick {
  year: number;
  x: number;
}

export interface ChronoLayout {
  /** Abscisse cible par identifiant. Vide s'il n'y a rien à placer. */
  x: Map<string, number>;
  /** Graduations à dessiner sous la frise, déjà espacées lisiblement. */
  ticks: ChronoTick[];
  /** Centre de la colonne des sources sans date, `null` s'il n'y en a aucune. */
  undatedX: number | null;
  /**
   * Abscisse du filet de rupture qui détache cette colonne de la frise.
   *
   * `null` quand tout est daté (rien à détacher) et quand rien ne l'est (il n'y
   * a alors pas de frise dont se détacher).
   */
  breakX: number | null;
  /** Combien de sources n'ont pas de date exploitable. */
  undatedCount: number;
  minYear: number | null;
  maxYear: number | null;
}

/**
 * Année de publication, ou `null` si la donnée ne permet pas de l'affirmer.
 *
 * Accepte une date ISO comme une année seule, parce que les imports viennent de
 * sources hétérogènes (Crossref donne une date complète, un scraping HTML peut
 * ne donner que « 2019 »). Rejette tout ce qui reste : mieux vaut « sans date »
 * qu'une année tirée d'une chaîne qu'on n'a pas comprise.
 */
export function yearOf(published_at: string | null | undefined): number | null {
  if (!published_at) return null;
  const m = /^\s*(-?\d{1,4})(?:-|\s|$)/.exec(published_at);
  if (!m) return null;
  const y = Number(m[1]);
  // Une année à 3 chiffres est plausible (manuscrit ancien) ; au-delà de
  // l'année prochaine, c'est une coquille d'import, pas une prédiction.
  if (!Number.isFinite(y) || y === 0 || y > new Date().getFullYear() + 1) return null;
  return y;
}

/** Pas de graduation le plus fin qui tienne dans `maxTicks` étiquettes. */
function niceStep(span: number, maxTicks: number): number {
  const raw = Math.max(1, span / Math.max(1, maxTicks));
  for (const step of [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]) {
    if (step >= raw) return step;
  }
  return 1000;
}

/**
 * Place chaque source sur une frise horizontale bornée par `width`.
 *
 * `width` est la largeur utile du repère du graphe, pas celle de l'écran : la
 * simulation reste libre en ordonnée, seule l'abscisse est contrainte.
 */
export function chronoLayout(items: ChronoItem[], width: number): ChronoLayout {
  const x = new Map<string, number>();
  const years = new Map<string, number>();
  let undatedCount = 0;

  for (const item of items) {
    const y = yearOf(item.published_at);
    if (y === null) undatedCount += 1;
    else years.set(item.id, y);
  }

  const empty: ChronoLayout = {
    x,
    ticks: [],
    undatedX: null,
    breakX: null,
    undatedCount,
    minYear: null,
    maxYear: null,
  };

  const values = [...years.values()];
  if (values.length === 0) {
    // Rien de daté : la frise n'aurait aucun sens, tout le monde est « sans
    // date » et reste au centre plutôt que dans une colonne marginale.
    if (undatedCount > 0) {
      const cx = width / 2;
      for (const item of items) x.set(item.id, cx);
      return { ...empty, undatedX: cx };
    }
    return empty;
  }

  const minYear = Math.min(...values);
  const maxYear = Math.max(...values);

  const left = 0;
  const right =
    undatedCount > 0
      ? Math.max(left + 1, width - UNDATED_GUTTER - UNDATED_BAND)
      : Math.max(left + 1, width);
  const breakX = undatedCount > 0 ? right + UNDATED_GUTTER / 2 : null;
  const undatedX = undatedCount > 0 ? right + UNDATED_GUTTER + UNDATED_BAND / 2 : null;
  const span = maxYear - minYear;

  const at = (year: number): number =>
    span === 0 ? (left + right) / 2 : left + ((year - minYear) / span) * (right - left);

  for (const item of items) {
    const y = years.get(item.id);
    x.set(item.id, y === undefined ? (undatedX as number) : at(y));
  }

  const ticks: ChronoTick[] = [];
  if (span === 0) {
    ticks.push({ year: minYear, x: at(minYear) });
  } else {
    const step = niceStep(span, 8);
    const first = Math.ceil(minYear / step) * step;
    for (let year = first; year <= maxYear; year += step) {
      ticks.push({ year, x: at(year) });
    }
    // Sans les bornes, une frise 1998-2024 graduée tous les 5 ans commencerait
    // à 2000 : le lecteur croirait la plus vieille source de 2000.
    if (ticks.length === 0 || ticks[0].year !== minYear) {
      ticks.unshift({ year: minYear, x: at(minYear) });
    }
    if (ticks[ticks.length - 1].year !== maxYear) {
      ticks.push({ year: maxYear, x: at(maxYear) });
    }
  }

  return { x, ticks, undatedX, breakX, undatedCount, minYear, maxYear };
}
