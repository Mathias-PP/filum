import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/**
 * La meme fiche, en markdown, a une adresse devinable.
 *
 * Un agent conversationnel a qui on donne `/@createur/fiche` recupere du HTML :
 * il doit en extraire la bibliographie, et c'est la qu'il invente. Suffixer
 * `.md` lui rend le meme contenu deja structure — titres, liste de sources,
 * DOI, rétractations, archives — sans qu'il ait a deviner un schema d'API.
 *
 * Le corps vient de l'export markdown du backend : une seule serialisation,
 * donc aucune divergence possible entre ce qu'on telecharge et ce qu'on lit.
 * Seule difference, l'entete — un export se telecharge, cette adresse se lit
 * sur place, d'ou l'absence de `content-disposition: attachment`.
 */
export const GET: RequestHandler = async ({ fetch, params }) => {
  const res = await fetch(`/api/v1/@${params.creator}/${params.card}/export?format=markdown`);
  // Le backend repond deja 404 pour une fiche privee comme pour une fiche
  // inexistante, afin de ne pas confirmer qu'elle existe. On relaie tel quel.
  if (res.status === 404) error(404, 'Fiche non trouvée');
  if (!res.ok) error(res.status, 'Erreur de chargement');

  return new Response(await res.text(), {
    headers: {
      'content-type': 'text/markdown; charset=utf-8',
      'cache-control': 'public, max-age=300',
    },
  });
};
