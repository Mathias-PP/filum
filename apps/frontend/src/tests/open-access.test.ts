import { describe, expect, it } from 'vitest';

import {
  freeReadUrl,
  licenseLabel,
  openAccessBadge,
  openAccessTitle,
} from '$lib/utils/open-access';

describe('openAccessBadge', () => {
  it('n’affiche rien tant que rien n’a été vérifié', () => {
    // null = jamais vérifié. Afficher « payant » serait une affirmation que
    // rien ne soutient.
    expect(openAccessBadge(null)).toBeNull();
    expect(openAccessBadge(undefined)).toBeNull();
    expect(openAccessBadge('')).toBeNull();
  });

  it('distingue « payant » de « non vérifié »', () => {
    const closed = openAccessBadge('closed')!;
    const unverifiable = openAccessBadge('unverifiable')!;
    expect(closed.label).not.toBe(unverifiable.label);
    expect(closed.isFree).toBe(false);
    expect(unverifiable.isFree).toBe(false);
  });

  it('marque comme gratuites les six routes d’accès libre', () => {
    for (const s of ['diamond', 'gold', 'green', 'hybrid', 'bronze', 'open']) {
      expect(openAccessBadge(s)?.isFree).toBe(true);
    }
  });

  it('ne promet pas la version publiée pour un dépôt en archive ouverte', () => {
    expect(openAccessBadge('green')!.help).toContain('différer');
  });

  it('encaisse un état inconnu du backend sans casser le rendu', () => {
    expect(openAccessBadge('platinum_2030')).toBeNull();
  });
});

describe('openAccessTitle', () => {
  it('date l’affirmation quand la vérification a eu lieu', () => {
    expect(openAccessTitle('closed', '2026-08-03T10:00:00')).toContain('03/08/2026');
  });

  it('reste lisible sans date', () => {
    const t = openAccessTitle('gold', null);
    expect(t.length).toBeGreaterThan(0);
    expect(t).not.toContain('vérifié le');
  });

  it('ignore une date inexploitable plutôt que d’afficher « Invalid Date »', () => {
    expect(openAccessTitle('gold', 'pas une date')).not.toContain('Invalid');
  });

  it('renvoie une chaîne vide quand il n’y a rien à dire', () => {
    expect(openAccessTitle(null, '2026-08-03T10:00:00')).toBe('');
  });
});

describe('freeReadUrl', () => {
  it('ouvre la version gratuite quand elle existe', () => {
    expect(freeReadUrl('gold', 'https://x.org/a.pdf')).toBe('https://x.org/a.pdf');
  });

  it('n’offre aucun bouton sur une référence payante', () => {
    // Même si une URL traînait, elle ne mènerait pas à une version gratuite.
    expect(freeReadUrl('closed', 'https://x.org/a.pdf')).toBeNull();
    expect(freeReadUrl('unverifiable', 'https://x.org/a.pdf')).toBeNull();
  });

  it('préfère aucun bouton à un bouton qui ne mène nulle part', () => {
    expect(freeReadUrl('green', null)).toBeNull();
    expect(freeReadUrl('green', '  ')).toBeNull();
    expect(freeReadUrl('green', 'javascript:alert(1)')).toBeNull();
  });

  it('ne fait rien tant que rien n’a été vérifié', () => {
    expect(freeReadUrl(null, 'https://x.org/a.pdf')).toBeNull();
  });
});

describe('licenseLabel', () => {
  it('rend une licence Creative Commons lisible', () => {
    expect(licenseLabel('cc-by')).toBe('CC BY');
    expect(licenseLabel('cc-by-nc-nd')).toBe('CC BY NC ND');
  });

  it('laisse intacte une licence qu’il ne sait pas mettre en forme', () => {
    expect(licenseLabel('publisher-specific-oa')).toBe('publisher-specific-oa');
  });

  it('renvoie null plutôt qu’une mention vide', () => {
    expect(licenseLabel(null)).toBeNull();
    expect(licenseLabel('   ')).toBeNull();
  });
});
