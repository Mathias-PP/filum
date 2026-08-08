/** Ce que le panneau d'export à la carte écrit dans l'adresse.
 *
 * Une case cochée qui n'arrive pas jusqu'au serveur ne casse rien de visible :
 * le téléchargement réussit, le fichier est simplement amputé. C'est le seul
 * endroit de cette fonctionnalité où l'erreur serait silencieuse.
 */

import { describe, expect, it } from 'vitest';

import {
  buildExportUrl,
  emptyScope,
  fullScope,
  serialiseDegrees,
  serialiseScope,
} from '$lib/export-query';

const BASE = 'https://api.philum/api/v1/@mp/fiche/export';

describe('serialiseScope', () => {
  it('rend les sections dans un ordre stable', () => {
    expect(serialiseScope(fullScope())).toBe('annotations,excerpts,archives,reliability');
  });

  it('rend une chaine vide quand rien nest coche', () => {
    expect(serialiseScope(emptyScope())).toBe('');
  });

  it('ne garde que ce qui est coche', () => {
    expect(serialiseScope({ ...emptyScope(), excerpts: true, archives: true })).toBe(
      'excerpts,archives'
    );
  });
});

describe('serialiseDegrees', () => {
  it('numerote a partir de 1', () => {
    expect(serialiseDegrees([{ ...emptyScope(), excerpts: true }, emptyScope()])).toBe(
      '1:excerpts|2:'
    );
  });
});

describe('buildExportUrl', () => {
  const req = {
    format: 'markdown',
    scope: { ...emptyScope(), excerpts: true },
    cited: [],
    citing: [],
  };

  it('ecrit un include vide plutot que de lomettre', () => {
    // Sans ca, decocher les quatre cases serait sans effet : `include` absent
    // veut dire « tout » cote serveur.
    const url = buildExportUrl(BASE, { ...req, scope: emptyScope() });
    expect(new URL(url).searchParams.get('include')).toBe('');
  });

  it('nenvoie pas de perimetre aux formats bibliographiques', () => {
    const url = new URL(buildExportUrl(BASE, { ...req, format: 'bibtex' }));
    expect(url.searchParams.has('include')).toBe(false);
  });

  it('nenvoie aucun sens de voisinage quand aucun degre nest demande', () => {
    const url = new URL(buildExportUrl(BASE, req));
    expect(url.searchParams.has('cited')).toBe(false);
    expect(url.searchParams.has('citing')).toBe(false);
  });

  it('distingue les deux sens', () => {
    const url = new URL(
      buildExportUrl(BASE, { ...req, cited: [fullScope()], citing: [emptyScope()] })
    );
    expect(url.searchParams.get('cited')).toBe('1:annotations,excerpts,archives,reliability');
    expect(url.searchParams.get('citing')).toBe('1:');
  });

  it('nenvoie pas de voisinage a un format qui ne sait pas le porter', () => {
    const url = new URL(buildExportUrl(BASE, { ...req, format: 'docx', cited: [fullScope()] }));
    expect(url.searchParams.has('cited')).toBe(false);
    expect(url.searchParams.get('include')).toBe('excerpts');
  });
});
