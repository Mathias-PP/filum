import { describe, expect, it } from 'vitest';

import { noticeUrl, retractionBadge, retractionTitle } from '$lib/utils/retraction';

describe('retractionBadge', () => {
  it('n’affiche rien tant que rien n’a été vérifié', () => {
    // null = jamais vérifié. Afficher quoi que ce soit serait une affirmation
    // que rien ne soutient.
    expect(retractionBadge(null)).toBeNull();
    expect(retractionBadge(undefined)).toBeNull();
    expect(retractionBadge('')).toBeNull();
  });

  it('distingue « aucun avis » de « non vérifiable »', () => {
    const none = retractionBadge('none')!;
    const unverifiable = retractionBadge('unverifiable')!;
    expect(none.label).not.toBe(unverifiable.label);
    expect(none.isNotice).toBe(false);
    expect(unverifiable.isNotice).toBe(false);
  });

  it('marque comme avis les trois états qui appellent une lecture', () => {
    for (const s of ['retracted', 'concern', 'corrected']) {
      expect(retractionBadge(s)?.isNotice).toBe(true);
    }
  });

  it('encaisse un état inconnu du backend sans casser le rendu', () => {
    expect(retractionBadge('withdrawn_2030')).toBeNull();
  });
});

describe('retractionTitle', () => {
  it('date l’affirmation quand la vérification a eu lieu', () => {
    const t = retractionTitle('none', '2026-08-03T10:00:00');
    expect(t).toContain('03/08/2026');
  });

  it('reste lisible sans date', () => {
    const t = retractionTitle('none', null);
    expect(t.length).toBeGreaterThan(0);
    expect(t).not.toContain('vérifié le');
  });

  it('ignore une date inexploitable plutôt que d’afficher « Invalid Date »', () => {
    expect(retractionTitle('none', 'pas une date')).not.toContain('Invalid');
  });

  it('renvoie une chaîne vide quand il n’y a rien à dire', () => {
    expect(retractionTitle(null, '2026-08-03T10:00:00')).toBe('');
  });
});

describe('noticeUrl', () => {
  it('construit un lien résolvable vers l’avis', () => {
    expect(noticeUrl('10.1016/S0140-6736(10)60175-4')).toBe(
      'https://doi.org/10.1016/S0140-6736(10)60175-4'
    );
  });

  it('renvoie null plutôt qu’un lien mort', () => {
    expect(noticeUrl(null)).toBeNull();
    expect(noticeUrl('  ')).toBeNull();
  });
});
