import eslintConfigPrettier from 'eslint-config-prettier'
import globals from 'globals'
import tseslint from 'typescript-eslint'

// Set up as omnicompy's is, without the Vue: typescript-eslint's
// recommended rules, with formatting left to prettier.
export default tseslint.config(
  {
    ignores: [
      'dist/**',
      'node_modules/**',
      'coverage-frontend/**',
      'playwright-report/**',
      'test-results/**',
      'var/**',
      'python/**',
    ],
  },
  ...tseslint.configs.recommended,
  {
    files: ['**/*.ts', '**/*.mts'],
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      // A leading underscore marks a parameter kept for its place
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_' },
      ],
    },
  },
  {
    // Node-side files: the build and test tooling
    files: ['*.mts', '*.ts', 'scripts/**', 'tests/**', '*.js'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
  {
    // The legacy CommonJS entry point, where require is the whole job
    files: ['domino-shim.js'],
    languageOptions: { sourceType: 'commonjs' },
    rules: { '@typescript-eslint/no-require-imports': 'off' },
  },
  eslintConfigPrettier
)
