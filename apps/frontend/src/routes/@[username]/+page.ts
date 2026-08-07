import { error } from '@sveltejs/kit';

import type { PageLoad } from './$types';
import type { UserProfile } from '$lib/api';

export const ssr = true;

// Le profil se chargeait en $effect : un crawler ne recevait qu'une coquille,
// et un slug inexistant repondait 200 (soft-404) au lieu de 404.
export const load: PageLoad = async ({ fetch, params }) => {
  const res = await fetch(`/api/v1/users/@${params.username}`);
  if (res.status === 404) error(404, 'Profil non trouvé');
  if (!res.ok) error(res.status, 'Erreur de chargement');
  const profile: UserProfile = await res.json();
  return { profile, username: params.username ?? '' };
};
