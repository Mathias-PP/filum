import { writable } from 'svelte/store';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'filum-theme';

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  const stored = window.localStorage.getItem(STORAGE_KEY) as Theme | null;
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return;
  document.documentElement.classList.toggle('dark', theme === 'dark');
  document.documentElement.style.colorScheme = theme;
}

function createTheme() {
  const initial: Theme = typeof window === 'undefined' ? 'light' : getInitialTheme();
  const { subscribe, set, update } = writable<Theme>(initial);

  if (typeof window !== 'undefined') {
    applyTheme(initial);
  }

  return {
    subscribe,
    set: (value: Theme) => {
      set(value);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(STORAGE_KEY, value);
        applyTheme(value);
      }
    },
    toggle: () =>
      update((value) => {
        const next: Theme = value === 'dark' ? 'light' : 'dark';
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(STORAGE_KEY, next);
          applyTheme(next);
        }
        return next;
      }),
  };
}

export const theme = createTheme();
