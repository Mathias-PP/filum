import { describe, expect, it } from 'vitest';
import { coinsTitle } from '$lib/utils/coins';

const carte = {
  title: 'A quoi sert le sommeil',
  content_authors: 'Mathias Pinault',
  published_at: '2026-05-12T10:00:00Z',
  content_url: 'https://www.youtube.com/watch?v=abc',
  format: 'video',
};

describe('coinsTitle', () => {
  it('declare le contexte OpenURL attendu par Zotero', () => {
    const t = coinsTitle(carte as never);
    expect(t).toContain('ctx_ver=Z39.88-2004');
    expect(t).toContain('rft_val_fmt=info%3Aofi%2Ffmt%3Akev%3Amtx%3Adc');
  });

  it('porte le genre, seul champ qui distingue un billet d un article', () => {
    expect(coinsTitle(carte as never)).toContain('rft.genre=');
  });

  it('encode le titre sans casser la chaine', () => {
    expect(coinsTitle(carte as never)).toContain(encodeURIComponent('A quoi sert le sommeil'));
  });
});
