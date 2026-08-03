import { describe, expect, it } from 'vitest';

import { UNDATED_BAND, chronoLayout, yearOf } from '$lib/utils/graph-chrono';

const item = (id: string, published_at: string | null) => ({ id, published_at });

describe('yearOf', () => {
  it('lit une date ISO complète', () => {
    expect(yearOf('2019-04-12T00:00:00')).toBe(2019);
    expect(yearOf('2019-04-12')).toBe(2019);
  });

  it('accepte une année seule, comme en renvoie un scraping HTML', () => {
    expect(yearOf('1998')).toBe(1998);
  });

  it('préfère « sans date » à une année devinée', () => {
    // Mieux vaut une colonne « sans date » qu'une position sur la frise que
    // personne n'a vérifiée.
    expect(yearOf('printemps dernier')).toBeNull();
    expect(yearOf(null)).toBeNull();
    expect(yearOf('')).toBeNull();
    expect(yearOf(undefined)).toBeNull();
  });

  it('rejette une année future, qui trahit une coquille d’import', () => {
    expect(yearOf('9999-01-01')).toBeNull();
  });

  it('accepte un manuscrit ancien à trois chiffres', () => {
    expect(yearOf('842')).toBe(842);
  });
});

describe('chronoLayout', () => {
  it('ordonne les abscisses comme les années', () => {
    const l = chronoLayout([item('a', '2020'), item('b', '1990'), item('c', '2005')], 1000);
    expect(l.x.get('b')!).toBeLessThan(l.x.get('c')!);
    expect(l.x.get('c')!).toBeLessThan(l.x.get('a')!);
    expect(l.minYear).toBe(1990);
    expect(l.maxYear).toBe(2020);
  });

  it('gare les sources sans date hors de la frise, jamais dessus', () => {
    const l = chronoLayout([item('a', '1990'), item('b', '2020'), item('x', null)], 1000);
    expect(l.undatedCount).toBe(1);
    expect(l.x.get('x')).toBe(l.undatedX);
    expect(l.x.get('x')!).toBeLessThan(l.x.get('a')!);
    expect(l.x.get('x')!).toBeLessThanOrEqual(UNDATED_BAND);
  });

  it('ne réserve aucune colonne quand tout est daté', () => {
    const l = chronoLayout([item('a', '1990'), item('b', '2020')], 1000);
    expect(l.undatedX).toBeNull();
    expect(l.undatedCount).toBe(0);
    expect(l.x.get('a')).toBe(0);
  });

  it('centre tout le monde quand rien n’est daté', () => {
    // Une frise sans une seule année serait un axe qui ne mesure rien.
    const l = chronoLayout([item('a', null), item('b', 'sans')], 800);
    expect(l.ticks).toEqual([]);
    expect(l.minYear).toBeNull();
    expect(l.x.get('a')).toBe(400);
    expect(l.x.get('b')).toBe(400);
  });

  it('n’écrase pas tout à gauche quand une seule année est représentée', () => {
    const l = chronoLayout([item('a', '2011'), item('b', '2011')], 1000);
    expect(l.x.get('a')).toBe(l.x.get('b'));
    expect(l.x.get('a')!).toBeGreaterThan(0);
    expect(l.ticks).toEqual([{ year: 2011, x: l.x.get('a')! }]);
  });

  it('gradue les bornes réelles, pas seulement les décennies rondes', () => {
    // Une frise 1998-2024 graduée tous les 5 ans commencerait à 2000 : le
    // lecteur croirait la plus vieille source de 2000.
    const l = chronoLayout([item('a', '1998'), item('b', '2024')], 1000);
    expect(l.ticks[0].year).toBe(1998);
    expect(l.ticks[l.ticks.length - 1].year).toBe(2024);
  });

  it('garde un nombre de graduations lisible sur un siècle', () => {
    const l = chronoLayout([item('a', '1920'), item('b', '2020')], 1000);
    expect(l.ticks.length).toBeLessThanOrEqual(10);
    expect(l.ticks.length).toBeGreaterThan(2);
  });

  it('ne renvoie rien à placer quand il n’y a rien', () => {
    const l = chronoLayout([], 1000);
    expect(l.x.size).toBe(0);
    expect(l.ticks).toEqual([]);
    expect(l.undatedX).toBeNull();
  });

  it('donne une abscisse à chaque source, datée ou non', () => {
    const items = [item('a', '2000'), item('b', null), item('c', '2010')];
    const l = chronoLayout(items, 900);
    for (const i of items) expect(l.x.get(i.id)).toBeTypeOf('number');
  });
});
