import { defineConfig } from 'vitest/config';

// Configuração separada do vite.config.ts: o Vitest 2 da raiz traz o próprio
// Vite 5, e os plugins do Vite 8 não carregam nele. O JSX dos testes é
// transformado pelo esbuild.
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  test: {
    css: false,
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
