import { describe, it, expect } from 'vitest';
import { SOURCE_COLORS } from '$lib/utils/source-colors';

const ALL_TYPES = [
  'peer-reviewed',
  'institutional',
  'press',
  'video',
  'image',
  'original',
] as const;

describe('SOURCE_COLORS', () => {
  it('defines a color entry for every SourceType', () => {
    for (const type of ALL_TYPES) {
      expect(SOURCE_COLORS[type]).toBeDefined();
    }
  });

  it('every entry has required color fields', () => {
    for (const type of ALL_TYPES) {
      const c = SOURCE_COLORS[type];
      expect(c.label).toBeTruthy();
      expect(c.fill).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(c.stroke).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(c.text).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(c.bgClass).toBeTruthy();
    }
  });
});
