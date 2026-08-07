import type { ContentType, Platform } from '$lib/api/types';

/**
 * Hôtes des grands éditeurs scientifiques. Liste explicite plutôt que motif :
 * « revue » n'a pas de marqueur dans un nom de domaine, et deviner à partir
 * d'un mot-clé classerait des blogs universitaires en revues.
 */
const REVUE_HOSTS = [
  'nature.com',
  'sciencedirect.com',
  'science.org',
  'sciencemag.org',
  'cell.com',
  'thelancet.com',
  'nejm.org',
  'plos.org',
  'frontiersin.org',
  'springer.com',
  'springeropen.com',
  'wiley.com',
  'tandfonline.com',
  'sagepub.com',
  'pnas.org',
  'bmj.com',
  'acs.org',
  'aps.org',
  'oup.com',
  'cambridge.org',
  'jstor.org',
  'doi.org',
];

export function guessPlatform(u: string): { platform: Platform; contentType: ContentType } {
  let host: string;
  try {
    host = new URL(u).hostname.replace(/^www\./, '').toLowerCase();
  } catch {
    return { platform: 'other', contentType: 'article' };
  }
  if (host.includes('youtube.com') || host === 'youtu.be')
    return { platform: 'youtube', contentType: 'video' };
  if (host.includes('twitter.com') || host === 'x.com')
    return { platform: 'x', contentType: 'post' };
  if (host.includes('bsky.app')) return { platform: 'bluesky', contentType: 'post' };
  if (REVUE_HOSTS.some((h) => host === h || host.endsWith('.' + h)))
    return { platform: 'revue-scientifique', contentType: 'article' };
  if (host.includes('substack.com') || host.includes('medium.com'))
    return { platform: 'blog', contentType: 'article' };
  return { platform: 'other', contentType: 'article' };
}
