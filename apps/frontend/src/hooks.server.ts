import type { Handle } from '@sveltejs/kit';

/**
 * Content negotiation sur les fiches publiques.
 *
 * Un agent qui envoie `Accept: text/markdown` (ou `application/vnd.philum+json`)
 * sur l'URL canonique `/@createur/fiche` obtient directement le markdown (ou
 * le JSON structuré), sans avoir a deviner qu'il existe un suffixe `.md`.
 * C'est la voie recommandee par l'IETF pour offrir plusieurs
 * representations d'une meme ressource : une seule adresse, plusieurs formats.
 *
 * La reecriture se fait au niveau du chemin (SvelteKit remonte au routeur),
 * pas via un 302 : ainsi le client n'a rien a suivre et le corps arrive dans
 * la meme requete.
 */
const CARD_PATH_RE = /^\/@([^/]+)\/([^/.]+)$/;

export const handle: Handle = async ({ event, resolve }) => {
  const path = event.url.pathname;
  const match = CARD_PATH_RE.exec(path);

  if (match) {
    const accept = event.request.headers.get('accept') || '';
    // Ordre de preference explicite : markdown avant JSON, JSON avant HTML.
    // Un navigateur envoie `text/html,application/xhtml+xml,...,*/*;q=0.8`
    // dont le */* pourrait matcher n'importe quoi : on exige que le format
    // demande soit nomme explicitement.
    const wantsMarkdown =
      /\btext\/markdown\b/.test(accept) && !/\btext\/html\b/.test(accept);
    const wantsPhilumJson =
      /\bapplication\/vnd\.philum\+json\b/.test(accept) &&
      !/\btext\/html\b/.test(accept);

    if (wantsMarkdown || wantsPhilumJson) {
      const [, creator, card] = match;
      const suffix = wantsMarkdown ? '.md' : '.philum.json';
      // Reecrire le chemin interne sans changer l'URL visible : le client
      // reste sur /@createur/fiche, le routeur SvelteKit sert la variante.
      event.url.pathname = `/@${creator}/${card}${suffix}`;
    }
  }

  return resolve(event);
};
