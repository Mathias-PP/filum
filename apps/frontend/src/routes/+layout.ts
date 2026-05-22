import type { LayoutLoad } from './$types';

export const ssr = false;

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
