import { describe, expect, it } from 'vitest';

import {
  STANCE_ORDER,
  STANCE_STROKE_UNDECLARED,
  STANCE_STYLES,
  stanceStroke,
  stanceStyle,
} from '$lib/utils/stance';

describe('stanceStroke', () => {
  it('donne une couleur propre à chaque rapport déclaré', () => {
    const strokes = STANCE_ORDER.map(stanceStroke);
    expect(new Set(strokes).size).toBe(STANCE_ORDER.length);
    expect(strokes).not.toContain(STANCE_STROKE_UNDECLARED);
  });

  it('retombe sur le neutre quand rien n’est déclaré', () => {
    // Non déclaré n'est pas « mentionne » : le trait ne doit pas prendre la
    // couleur d'une position que personne n'a exprimée.
    expect(stanceStroke(null)).toBe(STANCE_STROKE_UNDECLARED);
    expect(stanceStroke(undefined)).toBe(STANCE_STROKE_UNDECLARED);
    expect(stanceStroke('')).toBe(STANCE_STROKE_UNDECLARED);
  });

  it('encaisse une valeur inconnue sans casser le rendu', () => {
    // Le backend peut servir une valeur que ce frontend ne connaît pas encore.
    expect(stanceStroke('refute-partiellement')).toBe(STANCE_STROKE_UNDECLARED);
  });
});

describe('stanceStyle', () => {
  it('renvoie null plutôt qu’un style vide quand rien n’est déclaré', () => {
    expect(stanceStyle(null)).toBeNull();
    expect(stanceStyle('inconnu')).toBeNull();
  });

  it('expose un libellé et une explication pour chaque valeur', () => {
    for (const key of STANCE_ORDER) {
      const style = STANCE_STYLES[key];
      expect(style.label.length).toBeGreaterThan(0);
      expect(style.help.length).toBeGreaterThan(0);
    }
  });

  it('couvre exactement les valeurs de l’ordre d’affichage', () => {
    expect([...STANCE_ORDER].sort()).toEqual(Object.keys(STANCE_STYLES).sort());
  });
});
