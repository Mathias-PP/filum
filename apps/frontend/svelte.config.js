import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
    alias: {
      $lib: 'src/lib',
      $components: 'src/lib/components',
      $stores: 'src/lib/stores',
      $api: 'src/lib/api',
      $utils: 'src/lib/utils',
    },
    // Pas de bloc `csrf` : le defaut de SvelteKit (verification de l'origine
    // des soumissions de formulaire) est ce qu'il nous faut. Il avait ete
    // desactive en meme temps que le reste de la config initiale, sans besoin
    // identifie ; or /api/[...path] relaie les POST vers le backend avec le
    // cookie de session, et celui-ci est pose en `SameSite=None` en prod --
    // une page tierce pouvait donc soumettre un formulaire authentifie. Les
    // deux etapes OAuth sont des GET, rien ne requiert de POST cross-origin.
  },
};

export default config;
