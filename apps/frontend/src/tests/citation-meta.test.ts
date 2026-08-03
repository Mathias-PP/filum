import { describe, expect, it } from 'vitest';

import {
  cardHighwireTags,
  highwireDate,
  sourceCoins,
  splitAuthors,
  year,
} from '$lib/utils/citation-meta';
import type { CardDetail, Source } from '$lib/api/types';

function decode(coins: string): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const pair of coins.split('&')) {
    const [k, v] = pair.split('=');
    const key = decodeURIComponent(k);
    out.set(key, [...(out.get(key) ?? []), decodeURIComponent(v)]);
  }
  return out;
}

const baseSource: Source = {
  id: 's1',
  url: 'https://example.com/a',
  title: 'Inhibitory control development',
  authors: null,
  published_at: null,
  format: 'texte',
  category: 'page-web',
  author_kind: 'individu',
  annotation: null,
  stance: null,
  is_pivot: false,
  archive_status: 'pending',
  archive_url: null,
  archive_timestamp: null,
  parent_source_id: null,
  conflict_of_interest: null,
  citations_count: null,
  subscribers_count: null,
  views_count: null,
  impact_factor: null,
  excerpts: [],
  created_at: '2026-01-01T00:00:00',
  updated_at: null,
};

const baseCard: CardDetail = {
  id: 'c1',
  slug: 'ma-fiche',
  title: 'Ma vidéo sur la mémoire',
  description: null,
  content_url: 'https://youtube.com/watch?v=abc',
  content_authors: null,
  platform: 'youtube',
  content_type: 'video',
  status: 'published',
  is_seed: false,
  visibility: 'public',
  published_at: '2026-03-04T10:00:00',
  created_at: '2026-03-01T10:00:00',
  updated_at: null,
  creator: {
    slug: 'mathias-pinault',
    display_name: 'Mathias',
    bio: null,
    avatar_url: null,
    public_key: 'k',
  },
  sources: [],
  stats: {
    total_sources: 0,
    chercheur: 0,
    media: 0,
    institution_publique: 0,
    individu: 0,
    archived_count: 0,
    all_archived: false,
  },
};

describe('splitAuthors', () => {
  it('sépare des auteurs « Nom Initiales » sur la virgule', () => {
    expect(splitAuthors('Kang W., Hernández S., Rahman M.')).toEqual([
      'Kang W.',
      'Hernández S.',
      'Rahman M.',
    ]);
  });

  it('recolle les initiales détachées par la virgule', () => {
    // « Diamond, A. » est UN auteur, pas deux. Sans ce recollage, Scholar
    // reçoit « A. » comme premier auteur et l'entrée devient inexploitable.
    expect(splitAuthors('Diamond, A., Ling, D.S.')).toEqual(['Diamond, A.', 'Ling, D.S.']);
  });

  it('donne la priorité au point-virgule, non ambigu', () => {
    expect(splitAuthors('Dubois, C.; Martin, P.')).toEqual(['Dubois, C.', 'Martin, P.']);
  });

  it('accepte les séparateurs textuels', () => {
    expect(splitAuthors('Alice Dupont and Bob Martin')).toEqual(['Alice Dupont', 'Bob Martin']);
  });

  it('renvoie une liste vide plutôt que des blancs', () => {
    expect(splitAuthors(null)).toEqual([]);
    expect(splitAuthors('   ')).toEqual([]);
    expect(splitAuthors(',,')).toEqual([]);
  });
});

describe('highwireDate', () => {
  it('formate en YYYY/MM/DD', () => {
    expect(highwireDate('2026-03-04T10:00:00Z')).toBe('2026/03/04');
  });

  it('conserve une année seule plutôt que de la perdre', () => {
    expect(highwireDate('1984')).toBe('1984');
  });

  it('renvoie null sur une date inexploitable', () => {
    expect(highwireDate(null)).toBeNull();
    expect(highwireDate('pas une date')).toBeNull();
  });

  it('year extrait les quatre premiers chiffres', () => {
    expect(year('2026-03-04T10:00:00Z')).toBe('2026');
    expect(year(null)).toBeNull();
  });
});

describe('cardHighwireTags', () => {
  it('expose les auteurs du contenu, pas le créateur Philum', () => {
    const card = { ...baseCard, content_authors: 'Diamond, A., Ling, D.S.' };
    const tags = cardHighwireTags(card, 'https://philum.app/@mathias-pinault/ma-fiche');
    const authors = tags.filter((t) => t.name === 'citation_author').map((t) => t.content);
    expect(authors).toEqual(['Diamond, A.', 'Ling, D.S.']);
  });

  it('retombe sur le créateur faute d’auteurs déclarés', () => {
    // Google Scholar exige titre + premier auteur + année, sinon il traite la
    // page comme dépourvue de métadonnées. Mieux vaut le créateur que rien.
    const tags = cardHighwireTags(baseCard, 'https://philum.app/x');
    const authors = tags.filter((t) => t.name === 'citation_author').map((t) => t.content);
    expect(authors).toEqual(['Mathias']);
  });

  it('fournit le triplet minimum exigé par Google Scholar', () => {
    const tags = cardHighwireTags(baseCard, 'https://philum.app/x');
    const names = tags.map((t) => t.name);
    expect(names).toContain('citation_title');
    expect(names).toContain('citation_author');
    expect(names).toContain('citation_publication_date');
  });

  it('retombe sur created_at quand la fiche n’est pas encore publiée', () => {
    const card = { ...baseCard, published_at: null };
    const tags = cardHighwireTags(card, 'https://philum.app/x');
    expect(tags.find((t) => t.name === 'citation_publication_date')?.content).toBe('2026/03/01');
  });
});

describe('sourceCoins', () => {
  it('utilise le contexte journal pour un article scientifique', () => {
    const s: Source = {
      ...baseSource,
      category: 'article-scientifique',
      authors: 'Kang W., Hernández S.',
      journal: 'Frontiers in Psychology',
      volume: '13',
      pages: '651547',
      doi: '10.3389/fpsyg.2022.651547',
      published_at: '2022-05-01T00:00:00',
    };
    const p = decode(sourceCoins(s));
    expect(p.get('rft_val_fmt')).toEqual(['info:ofi/fmt:kev:mtx:journal']);
    expect(p.get('rft.atitle')).toEqual(['Inhibitory control development']);
    expect(p.get('rft.jtitle')).toEqual(['Frontiers in Psychology']);
    expect(p.get('rft.date')).toEqual(['2022']);
    expect(p.get('rft.au')).toEqual(['Kang W.', 'Hernández S.']);
    expect(p.get('rft_id')).toContain('info:doi/10.3389/fpsyg.2022.651547');
  });

  it('utilise le contexte book pour un livre', () => {
    const s: Source = { ...baseSource, category: 'livre', publisher: 'Gallimard' };
    const p = decode(sourceCoins(s));
    expect(p.get('rft_val_fmt')).toEqual(['info:ofi/fmt:kev:mtx:book']);
    expect(p.get('rft.btitle')).toEqual(['Inhibitory control development']);
    expect(p.get('rft.pub')).toEqual(['Gallimard']);
  });

  it('retombe sur Dublin Core pour une vidéo ou une page web', () => {
    // Le cœur de l'agnosticité : sans le contexte dc, une source YouTube
    // devrait mentir sur son genre pour être exportable.
    const s: Source = { ...baseSource, category: 'documentaire', format: 'video' };
    const p = decode(sourceCoins(s));
    expect(p.get('rft_val_fmt')).toEqual(['info:ofi/fmt:kev:mtx:dc']);
    expect(p.get('rft.title')).toEqual(['Inhibitory control development']);
    expect(p.has('rft.atitle')).toBe(false);
  });

  it('retombe sur l’URL quand la source n’a pas de titre', () => {
    const s: Source = { ...baseSource, title: null };
    const p = decode(sourceCoins(s));
    expect(p.get('rft.title')).toEqual(['https://example.com/a']);
  });

  it('encode les caractères qui casseraient l’attribut', () => {
    const s: Source = { ...baseSource, title: 'Sucre & santé : l’étude' };
    const coins = sourceCoins(s);
    expect(coins).not.toContain('Sucre & santé');
    expect(decode(coins).get('rft.title')).toEqual(['Sucre & santé : l’étude']);
  });

  it('commence toujours par la version du contexte', () => {
    expect(sourceCoins(baseSource).startsWith('ctx_ver=Z39.88-2004')).toBe(true);
  });
});
