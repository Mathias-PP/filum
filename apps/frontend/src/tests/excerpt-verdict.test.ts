/**
 * Ce que la fiche publique a le droit d'affirmer d'une citation.
 *
 * Le risque n'est pas le plantage : c'est de dire un peu plus que ce qu'on
 * sait. Trois confusions à empêcher, chacune tenue par un test :
 * l'absence de relecture ne doit pas se lire comme une relecture, une page
 * illisible ne doit pas s'imputer à la citation, et une relecture contre un
 * texte fourni ne doit pas se présenter comme une relecture contre la source.
 */
import { describe, expect, it } from 'vitest';
import { lireVerdict } from '$lib/utils/excerpt-verdict';
import type { SourceExcerpt } from '$lib/api/types';

function extrait(p: Partial<SourceExcerpt> = {}): SourceExcerpt {
  return {
    id: 'x',
    position: 1,
    text: 'le sommeil joue un rôle actif',
    title: null,
    context: null,
    suggested_by_ai: false,
    annotated_by_ai: false,
    verified_at: null,
    verified_status: null,
    verified_text_source: null,
    ...p,
  };
}

describe('lireVerdict', () => {
  it('ne fait pas passer une citation jamais relue pour une citation relue', () => {
    const v = lireVerdict(extrait());
    expect(v.ton).toBe('inconnu');
    expect(v.label).toBe('Jamais relu');
    expect(v.detail).toMatch(/déclarée, pas vérifiée/);
  });

  it('date la relecture, sinon « relu » ne dit pas quand', () => {
    const v = lireVerdict(
      extrait({
        verified_at: '2026-08-08T10:00:00',
        verified_status: 'found',
        verified_text_source: 'fetched',
      })
    );
    expect(v.ton).toBe('verifie');
    expect(v.label).toMatch(/8 août 2026/);
  });

  it('ne présente pas un texte fourni comme la source elle-même', () => {
    const v = lireVerdict(
      extrait({
        verified_at: '2026-08-08T10:00:00',
        verified_status: 'found',
        verified_text_source: 'provided',
      })
    );
    // Le passage a bien été retrouvé, mais dans un texte que seul l'auteur·ice
    // atteste : le ton ne peut pas être celui d'une vérification reproductible.
    expect(v.ton).toBe('nuance');
    expect(v.label).toMatch(/texte fourni/);
    expect(v.detail).toMatch(/n'engage que sa parole/);
  });

  it("n'impute pas au citateur une page qui ne rend rien", () => {
    const v = lireVerdict(
      extrait({ verified_at: '2026-08-08T10:00:00', verified_status: 'unreadable' })
    );
    expect(v.ton).toBe('inconnu');
    expect(v.detail).toMatch(/ni dans un sens ni dans l'autre/);
    expect(v.label).not.toMatch(/[Ii]ntrouvable/);
  });

  it('distingue « reformulé depuis » de « introuvable »', () => {
    const bouge = lireVerdict(
      extrait({ verified_at: '2026-08-08T10:00:00', verified_status: 'moved' })
    );
    const absent = lireVerdict(
      extrait({ verified_at: '2026-08-08T10:00:00', verified_status: 'missing' })
    );
    expect(bouge.ton).toBe('nuance');
    expect(absent.ton).toBe('absent');
    expect(bouge.label).not.toBe(absent.label);
  });

  it('supporte une date absente sans afficher « Invalid Date »', () => {
    const v = lireVerdict(extrait({ verified_status: 'found', verified_at: null }));
    expect(v.label).toBe('Relu dans la source');
    expect(v.label).not.toMatch(/Invalid/);
  });
});
