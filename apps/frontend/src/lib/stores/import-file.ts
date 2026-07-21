import { writable } from 'svelte/store';

/**
 * Fichier bibliographique déposé sur le formulaire « Nouvelle fiche »,
 * transmis en mémoire à la page Sources (un File ne survit pas à une
 * navigation full-page, mais les navigations SvelteKit sont client-side).
 */
export const pendingImportFile = writable<File | null>(null);
