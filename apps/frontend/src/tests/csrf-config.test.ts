/**
 * La protection CSRF de SvelteKit est active par defaut, et doit le rester.
 *
 * `/api/[...path]` relaie les POST vers le backend en transportant le cookie
 * de session, pose en `SameSite=None` en production (le proxy existe pour que
 * les cookies survivent a l'ITP de Safari mobile). Desactiver `checkOrigin`
 * laissait donc une page tierce soumettre un formulaire authentifie.
 *
 * Ce test echoue si quelqu'un reintroduit le desamorcage, quelle que soit
 * l'option employee -- l'ancienne `checkOrigin` ou la nouvelle
 * `trustedOrigins: ['*']`.
 */

// @vitest-environment node
// jsdom fournit un TextEncoder qui ne produit pas de vrai Uint8Array ;
// esbuild, tire par l'adaptateur importe avec la config, refuse de demarrer.

import { describe, expect, it } from 'vitest';

import config from '../../svelte.config.js';

describe('configuration CSRF', () => {
  it("ne desactive pas la verification d'origine", () => {
    expect(config.kit?.csrf?.checkOrigin).not.toBe(false);
  });

  it("n'accorde pas une confiance universelle aux origines tierces", () => {
    expect(config.kit?.csrf?.trustedOrigins ?? []).not.toContain('*');
  });
});
