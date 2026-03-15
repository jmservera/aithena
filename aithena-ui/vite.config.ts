import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const rawApiUrl = process.env.VITE_API_URL?.trim();
const apiProxyTarget =
  !rawApiUrl || rawApiUrl === '.' ? 'http://localhost:8080' : rawApiUrl.replace(/\/+$/, '');

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react({ fastRefresh: false })],
  base: '',
  server: {
    proxy: {
      '/documents': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '/v1': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
  },
});
