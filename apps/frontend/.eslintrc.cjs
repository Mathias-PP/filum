module.exports = {
  root: true,
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended-type-checked',
    'plugin:svelte/recommended',
    'prettier'
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    sourceType: 'module',
    ecmaVersion: 2022,
    project: './tsconfig.json'
  },
  plugins: ['@typescript-eslint', 'svelte'],
  env: {
    browser: true,
    es2022: true,
    node: true
  },
  globals: {
    __DEV__: 'readonly'
  },
  rules: {
    'svelte/no-at-html-tags': 'off',
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    '@typescript-eslint/consistent-type-imports': [
      'error',
      { prefer: 'type imports', fixStyle: 'inline-type-imports' }
    ],
    '@typescript-eslint/promise-function-async': 'warn',
    'no-console': ['warn', { allow: ['warn', 'error'] }]
  },
  overrides: [
    {
      files: ['*.svelte'],
      parser: 'svelte-eslint-parser',
      parserOptions: {
        svelteConfig: {
          preprocess: {
            environment: 'browser'
          }
        }
      }
    }
  ]
}
