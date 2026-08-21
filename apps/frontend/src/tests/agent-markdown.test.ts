import { describe, expect, it } from 'vitest';

import { analyser, segmentsInline } from '$lib/agent/markdown';

describe('analyse des blocs', () => {
  it('sépare titres, paragraphes, listes, citation, code et séparateur', () => {
    const blocs = analyser(
      [
        '# Titre',
        '',
        'Un paragraphe.',
        '',
        '- un',
        '- deux',
        '',
        '1. premier',
        '2. deuxième',
        '',
        '> une citation',
        '```js',
        'let x = 1;',
        '```',
        '---',
      ].join('\n')
    );
    expect(blocs.map((b) => b.t)).toEqual([
      'titre',
      'paragraphe',
      'liste',
      'liste',
      'citation',
      'code',
      'separateur',
    ]);
    expect(blocs[0]).toMatchObject({ niveau: 1 });
    const puces = blocs[2] as Extract<(typeof blocs)[number], { t: 'liste' }>;
    expect(puces.ordonnee).toBe(false);
    expect(puces.items.map((item) => (item[0] as { texte: string }).texte)).toEqual(['un', 'deux']);
    expect(blocs[3]).toMatchObject({ ordonnee: true });
    expect(blocs[5]).toEqual({ t: 'code', texte: 'let x = 1;' });
  });

  it('regroupe les lignes contiguës en un seul paragraphe', () => {
    const blocs = analyser('ligne un\nligne deux');
    expect(blocs).toHaveLength(1);
    expect(blocs[0]).toMatchObject({
      t: 'paragraphe',
      segments: [{ t: 'texte', texte: 'ligne un ligne deux' }],
    });
  });

  it('rend le code verbatim même s’il contient du markdown', () => {
    const blocs = analyser('```\n**pas du gras**\n```');
    expect(blocs).toEqual([{ t: 'code', texte: '**pas du gras**' }]);
  });

  it('ne confond pas « --- » de séparation avec une puce', () => {
    const blocs = analyser('- item\n\n---\n\nsuite');
    expect(blocs.map((b) => b.t)).toEqual(['liste', 'separateur', 'paragraphe']);
  });
});

describe('segments en ligne', () => {
  it('reconnaît gras, italique, code et lien', () => {
    const segs = segmentsInline(
      'du **gras**, de *l’italique*, du `code` et [un lien](https://a.org)'
    );
    expect(segs).toEqual([
      { t: 'texte', texte: 'du ' },
      { t: 'gras', texte: 'gras' },
      { t: 'texte', texte: ', de ' },
      { t: 'italique', texte: 'l’italique' },
      { t: 'texte', texte: ', du ' },
      { t: 'code', code: 'code' },
      { t: 'texte', texte: ' et ' },
      { t: 'lien', texte: 'un lien', href: 'https://a.org' },
    ]);
  });

  it('refuse un lien au schéma dangereux et le rend comme texte', () => {
    const segs = segmentsInline('[cliquez](javascript:alert(1))');
    expect(segs).toEqual([{ t: 'texte', texte: '[cliquez](javascript:alert(1))' }]);
  });

  it('laisse le HTML brut en texte : jamais injecté', () => {
    const segs = segmentsInline('<script>alert(1)</script>');
    expect(segs).toEqual([{ t: 'texte', texte: '<script>alert(1)</script>' }]);
  });

  it('gère un mélange gras + italique collés', () => {
    const segs = segmentsInline('**a***b*');
    expect(segs).toEqual([
      { t: 'gras', texte: 'a' },
      { t: 'italique', texte: 'b' },
    ]);
  });
});
