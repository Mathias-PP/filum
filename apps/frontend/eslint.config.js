import js from '@eslint/js';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import sveltePlugin from 'eslint-plugin-svelte';
import svelteParser from 'svelte-eslint-parser';
import prettier from 'eslint-config-prettier';

export default [
  js.configs.recommended,
  prettier,
  {
    ignores: ['.svelte-kit/', 'build/', 'node_modules/', '*.cjs', '*.mjs'],
  },
  {
    files: ['**/*.ts', '**/*.svelte.ts'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { sourceType: 'module', ecmaVersion: 2022 },
    },
    plugins: { '@typescript-eslint': tsPlugin },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      'no-undef': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
  {
    files: ['**/*.svelte'],
    languageOptions: {
      parser: svelteParser,
      parserOptions: { parser: tsParser },
    },
    plugins: { svelte: sveltePlugin },
    rules: {
      ...sveltePlugin.configs.recommended.rules,
      'svelte/no-at-html-tags': 'off',
      'no-undef': 'off',
      'no-unused-vars': 'off',
    },
  },
  // Sandbox pages : outils internes de design, on relâche les contraintes a11y
  // (labels non liés, mousedown sur <circle>) qui ne s'appliquent pas vraiment
  // à un éditeur SVG interactif.
  {
    files: ['**/routes/sandbox/**/*.svelte'],
    rules: {
      'svelte/valid-compile': 'off',
    },
  },
];
