import { describe, expect, it } from 'vitest';
import { guessPlatform } from '$lib/utils/platform-guess';

describe('guessPlatform', () => {
  it('reconnaît les plateformes déjà couvertes', () => {
    expect(guessPlatform('https://www.youtube.com/watch?v=x')).toEqual({
      platform: 'youtube',
      contentType: 'video',
    });
    expect(guessPlatform('https://x.com/a/status/1')).toEqual({
      platform: 'x',
      contentType: 'post',
    });
    expect(guessPlatform('https://bsky.app/profile/a')).toEqual({
      platform: 'bluesky',
      contentType: 'post',
    });
    expect(guessPlatform('https://a.substack.com/p/b')).toEqual({
      platform: 'blog',
      contentType: 'article',
    });
  });

  // Constaté le 2026-08-04 en parcourant la création de fiche : une revue
  // scientifique retombait sur « Autre », faute de case. Ce n'était pas une
  // détection ratée mais une taxonomie incomplète — et « Autre » sur Nature
  // dit au lecteur que le support n'a pas de genre.
  it('reconnaît une revue scientifique', () => {
    for (const url of [
      'https://www.nature.com/articles/nrn3667',
      'https://www.sciencedirect.com/science/article/pii/S0896627301005839',
      'https://www.science.org/doi/10.1126/science.1152882',
      'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0001',
      'https://www.frontiersin.org/articles/10.3389/fpsyg.2022.651547/full',
      'https://link.springer.com/article/10.1007/s00426-019-01158-6',
      'https://onlinelibrary.wiley.com/doi/10.1002/hipo.20350',
      'https://www.thelancet.com/journals/lancet/article/PIIS0140-6736',
      'https://doi.org/10.1038/nrn3667',
    ]) {
      expect(guessPlatform(url), url).toEqual({
        platform: 'revue-scientifique',
        contentType: 'article',
      });
    }
  });

  it('ne confond pas un blog hébergé chez un éditeur', () => {
    // `nature.com` sert aussi des billets de blog ; le genre du support reste
    // celui de la revue, on ne cherche pas à trancher plus finement ici.
    expect(guessPlatform('https://exemple.fr/mon-billet')).toEqual({
      platform: 'other',
      contentType: 'article',
    });
  });

  it('une URL invalide ne fait pas deviner n’importe quoi', () => {
    expect(guessPlatform('pas une url')).toEqual({ platform: 'other', contentType: 'article' });
  });
});
