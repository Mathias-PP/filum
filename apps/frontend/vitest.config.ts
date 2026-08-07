import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  plugins: [svelte({ hot: false })],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/tests/**/*.test.ts'],
    setupFiles: [],
    passWithNoTests: true,
  },
  resolve: {
    // Sans cette condition, Svelte 5 sert sa version serveur et `mount()` lève
    // `lifecycle_function_unavailable` : aucun composant n'est montable, ce
    // qui se lisait comme « testing-library incompatible Svelte 5 ».
    conditions: ['browser'],
    alias: {
      $lib: path.resolve('./src/lib'),
      $components: path.resolve('./src/lib/components'),
      $stores: path.resolve('./src/lib/stores'),
      $api: path.resolve('./src/lib/api'),
    },
  },
});
