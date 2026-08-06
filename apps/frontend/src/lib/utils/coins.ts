/**
 * COinS : metadonnees OpenURL cachees dans l'attribut `title` d'un `<span>`.
 *
 * Mecanisme retenu plutot que JSON-LD parce que Zotero, qui est l'outil que
 * nos lecteurs n'abandonneront pas, ignore entierement JSON-LD. Seul le champ
 * `rft.genre` permet de distinguer un billet de blog d'un article, ce qui est
 * exactement la distinction que Philum doit porter.
 *
 * Le contexte `mtx:dc` (Dublin Core) est plus permissif que `mtx:journal` :
 * une fiche documente aussi bien une video qu'un rapport, et forcer un modele
 * d'article produirait des metadonnees fausses.
 */
import type { Card } from '$lib/api/types';

const GENRE_PAR_FORMAT: Record<string, string> = {
  video: 'unknown',
  audio: 'unknown',
  texte: 'article',
  data: 'dataset',
  image: 'unknown',
};

export function coinsTitle(card: Card): string {
  const parts: string[] = [
    'ctx_ver=Z39.88-2004',
    `rft_val_fmt=${encodeURIComponent('info:ofi/fmt:kev:mtx:dc')}`,
    `rft.type=${encodeURIComponent(card.format ?? 'webpage')}`,
    `rft.genre=${encodeURIComponent(GENRE_PAR_FORMAT[card.format ?? ''] ?? 'unknown')}`,
    `rft.title=${encodeURIComponent(card.title)}`,
  ];
  if (card.content_authors) {
    for (const author of card.content_authors.split(',')) {
      const trimmed = author.trim();
      if (trimmed) parts.push(`rft.au=${encodeURIComponent(trimmed)}`);
    }
  }
  if (card.published_at) {
    parts.push(`rft.date=${encodeURIComponent(card.published_at.slice(0, 10))}`);
  }
  if (card.content_url) {
    parts.push(`rft_id=${encodeURIComponent(card.content_url)}`);
  }
  return parts.join('&');
}
