import { writable, derived } from 'svelte/store';
import type { User } from '$lib/api';

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>({
    user: null,
    loading: true,
    error: null,
  });

  return {
    subscribe,
    setUser: (user: User | null) => update((s) => ({ ...s, user, loading: false })),
    setLoading: (loading: boolean) => update((s) => ({ ...s, loading })),
    setError: (error: string | null) => update((s) => ({ ...s, error, loading: false })),
    reset: () => set({ user: null, loading: false, error: null }),
  };
}

export const auth = createAuthStore();

export const isAuthenticated = derived(auth, ($auth) => !!$auth.user);
export const currentUser = derived(auth, ($auth) => $auth.user);
