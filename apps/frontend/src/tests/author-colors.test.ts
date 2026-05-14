import { describe, it, expect } from 'vitest';
import { AUTHOR_COLORS, formatLabel, categoryLabel } from '$lib/utils/author-colors';
import type { AuthorKind, SourceCategory, SourceFormat } from '$lib/api';

const ALL_AUTHOR_KINDS = [
  'chercheur',
  'media',
  'institution-publique',
  'gouvernement',
  'ecole',
  'laboratoire',
  'entreprise',
  'asso',
  'individu',
] as const satisfies readonly AuthorKind[];

const ALL_FORMATS = [
  'texte',
  'video',
  'image',
  'audio',
  'data',
] as const satisfies readonly SourceFormat[];

const ALL_CATEGORIES = [
  'article-scientifique',
  'preprint',
  'article-presse',
  'communique',
  'documentaire',
  'interview',
  'podcast',
  'blog',
  'post-social',
  'livre',
  'page-web',
  'notes',
] as const satisfies readonly SourceCategory[];

describe('AUTHOR_COLORS', () => {
  it('defines a color entry for every AuthorKind', () => {
    for (const kind of ALL_AUTHOR_KINDS) {
      expect(AUTHOR_COLORS[kind]).toBeDefined();
    }
  });

  it('every entry has well-formed color fields', () => {
    for (const kind of ALL_AUTHOR_KINDS) {
      const c = AUTHOR_COLORS[kind];
      expect(c.label).toBeTruthy();
      expect(c.fill).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(c.stroke).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(c.text).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(c.bgClass).toBeTruthy();
    }
  });
});

describe('label helpers', () => {
  it('returns a non-empty French label for every format', () => {
    for (const f of ALL_FORMATS) {
      expect(formatLabel(f)).toBeTruthy();
    }
  });

  it('returns a non-empty French label for every category', () => {
    for (const c of ALL_CATEGORIES) {
      expect(categoryLabel(c)).toBeTruthy();
    }
  });
});
