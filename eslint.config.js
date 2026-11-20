import base from '@precisa-saude/eslint-config/base';
import react from '@precisa-saude/eslint-config/react';

export default [
  { ignores: ['pipeline/**', 'data/**'] },
  ...base,
  ...react,
  {
    // eslint-plugin-react 7.37 detecta a versão do React com uma API removida
    // no ESLint 10 e quebra. Com a versão declarada, a detecção não roda.
    // Remover quando o preset de @precisa-saude/eslint-config corrigir isso.
    files: ['site/**/*.{ts,tsx}'],
    settings: { react: { version: '19.3' } },
  },
  {
    // Test files are excluded from package tsconfigs (to keep tsc --noEmit
    // tight), so disable type-aware parsing for them or ESLint errors
    // trying to locate a project.
    files: ['**/*.test.ts', '**/*.test.tsx', '**/*.spec.ts', '**/*.spec.tsx', '**/__tests__/**'],
    languageOptions: {
      parserOptions: { project: false },
    },
    rules: {
      '@typescript-eslint/consistent-type-imports': 'off',
      'max-lines': 'off',
      'max-lines-per-function': 'off',
    },
  },
];
