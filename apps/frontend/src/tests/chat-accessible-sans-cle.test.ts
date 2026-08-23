/**
 * Le chat doit rester atteignable sans clé d'API.
 *
 * `/dashboard/chat` cachait `ChatPanel` derrière `{#if defaut}` : sans clé
 * marquée par défaut, la page affichait un renvoi vers la page des clés. Or le
 * serveur sait répondre sans aucune clé, par le mode gratuit ou le mode
 * découverte, et le bouton qui déclenche le consentement au mode gratuit vit
 * dans `ChatPanel`. Le masquer enfermait le nouvel arrivant : pour atteindre la
 * fonctionnalité censée lui éviter d'ouvrir un compte chez un fournisseur, il
 * devait ouvrir un compte chez un fournisseur.
 *
 * Le test lit la source : monter cette page demanderait de simuler le routeur,
 * le client API et le flux SSE, pour ne vérifier au bout du compte que cette
 * condition de rendu.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const page = readFileSync(
  resolve(process.cwd(), 'src/routes/dashboard/chat/+page.svelte'),
  'utf-8'
);

describe('page /dashboard/chat', () => {
  it('rend le chat en dehors de la condition sur la clé par défaut', () => {
    const iChat = page.indexOf('<ChatPanel');
    expect(iChat, 'ChatPanel introuvable dans la page').toBeGreaterThan(-1);
    const iCondition = page.indexOf('{#if defaut}');
    expect(iCondition, 'condition sur la clé par défaut introuvable').toBeGreaterThan(-1);
    // La condition doit être refermée avant que le chat ne soit rendu.
    const avant = page.slice(iCondition, iChat);
    expect(avant, 'ChatPanel est encore enfermé dans {#if defaut}').toContain('{/if}');
  });

  it('ne promet le mode gratuit que si l’instance en propose un', () => {
    const iPromesse = page.indexOf('Mode gratuit');
    expect(iPromesse, 'mention du mode gratuit introuvable').toBeGreaterThan(-1);
    const avant = page.slice(0, iPromesse);
    expect(avant.lastIndexOf('{#if gratuitDisponible}')).toBeGreaterThan(
      avant.lastIndexOf('{/if}')
    );
  });
});
