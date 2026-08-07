import { redirect } from '@sveltejs/kit';

import type { LayoutLoad } from './$types';

// Zone authentifiee : rien a indexer, et le code suppose un navigateur.
export const ssr = false;

export const load: LayoutLoad = async ({ parent }) => {
  const data = await parent();
  if (!data.user) {
    redirect(302, '/');
  }
};
