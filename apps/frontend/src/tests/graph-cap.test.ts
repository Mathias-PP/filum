import { describe, expect, it } from 'vitest';

import { capSources } from '$lib/utils/graph-cap';

interface S {
  id: string;
  parent_source_id: string | null;
  is_pivot?: boolean;
}

const flat = (n: number, offset = 0): S[] =>
  Array.from({ length: n }, (_, i) => ({ id: `s${i + offset}`, parent_source_id: null }));

describe('capSources', () => {
  it('ne touche à rien tant que la fiche tient à l’écran', () => {
    const s = flat(10);
    const r = capSources(s, 60);
    expect(r.kept).toBe(s);
    expect(r.hiddenCount).toBe(0);
  });

  it('garde exactement la limite quand rien ne dépend de rien', () => {
    const r = capSources(flat(152), 60);
    expect(r.kept).toHaveLength(60);
    expect(r.hiddenCount).toBe(92);
  });

  it('respecte l’ordre de la fiche plutôt qu’un classement maison', () => {
    const r = capSources(flat(100), 5);
    expect(r.kept.map((s) => s.id)).toEqual(['s0', 's1', 's2', 's3', 's4']);
  });

  it('fait passer les sources clés devant, même en fin de fiche', () => {
    // Le seul classement admis est celui que l'auteur·rice a déclaré.
    const sources: S[] = [...flat(50), { id: 'cle', parent_source_id: null, is_pivot: true }];
    expect(capSources(sources, 3).kept.map((s) => s.id)).toContain('cle');
  });

  it('garde l’ordre de la fiche entre sources clés', () => {
    const sources: S[] = [
      { id: 'k1', parent_source_id: null, is_pivot: true },
      ...flat(50),
      { id: 'k2', parent_source_id: null, is_pivot: true },
    ];
    const r = capSources(sources, 2);
    expect(r.kept.map((s) => s.id)).toEqual(['k1', 'k2']);
  });

  it('remonte le parent d’une source retenue', () => {
    // Sans ça, la source secondaire flotterait détachée : le graphe montrerait
    // une filiation dont l'origine a disparu.
    const sources: S[] = [
      ...flat(3),
      { id: 'child', parent_source_id: 'ancestor' },
      ...flat(50, 100),
      { id: 'ancestor', parent_source_id: null },
    ];
    const r = capSources(sources, 4);
    const ids = r.kept.map((s) => s.id);
    expect(ids).toContain('child');
    expect(ids).toContain('ancestor');
  });

  it('remonte toute la chaîne, pas seulement un cran', () => {
    const sources: S[] = [
      { id: 'c', parent_source_id: 'b' },
      ...flat(50, 100),
      { id: 'b', parent_source_id: 'a' },
      { id: 'a', parent_source_id: null },
    ];
    const ids = capSources(sources, 1).kept.map((s) => s.id);
    expect(ids).toEqual(['c', 'b', 'a']);
  });

  it('compte comme caché ce qui l’est vraiment, parents remontés déduits', () => {
    const sources: S[] = [
      { id: 'c', parent_source_id: 'a' },
      ...flat(10, 100),
      { id: 'a', parent_source_id: null },
    ];
    const r = capSources(sources, 2);
    expect(r.kept).toHaveLength(3);
    expect(r.hiddenCount).toBe(sources.length - 3);
  });

  it('ne fige pas la page sur une filiation circulaire', () => {
    // Donnée invalide, mais un rendu de page publique ne doit jamais partir en
    // boucle infinie à cause d'elle.
    const sources: S[] = [
      { id: 'a', parent_source_id: 'b' },
      { id: 'b', parent_source_id: 'a' },
      ...flat(10, 100),
    ];
    const r = capSources(sources, 1);
    expect(r.kept.map((s) => s.id).sort()).toEqual(['a', 'b']);
  });

  it('ignore un parent introuvable sans casser', () => {
    const sources: S[] = [{ id: 'a', parent_source_id: 'disparu' }, ...flat(10, 100)];
    expect(capSources(sources, 1).kept.map((s) => s.id)).toEqual(['a']);
  });

  it('une limite nulle ou négative désactive le bornage', () => {
    const s = flat(200);
    expect(capSources(s, 0).kept).toBe(s);
    expect(capSources(s, -1).hiddenCount).toBe(0);
  });
});
