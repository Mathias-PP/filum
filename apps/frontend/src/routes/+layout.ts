import type { LayoutLoad } from './$types';

// Rendu serveur par defaut. Sans lui un crawler ne recoit qu'une coquille vide :
// c'est ce qui rendait l'accueil, les pages vitrine et les profils invisibles
// pour les moteurs, donc absents de l'index — et une couche de navigation IA qui
// ne trouve rien dans l'index ne tente jamais le GET de l'URL qu'on lui donne.
// Les zones authentifiees s'en exemptent (dashboard, auth, sandbox) : rien a
// indexer, et elles supposent un navigateur.
export const ssr = true;

export const load: LayoutLoad = async ({ fetch }) => {
  // Relative — routed through the SvelteKit /api proxy for first-party cookies.
  const response = await fetch('/api/v1/auth/me', {
    credentials: 'include',
  });

  if (response.ok) {
    const user = await response.json();
    return { user };
  }

  return { user: null };
};
