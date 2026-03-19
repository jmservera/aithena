import { readFileSync } from 'fs';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const __dirname = dirname(fileURLToPath(import.meta.url));

const rawApiUrl = process.env.VITE_API_URL?.trim();
const apiProxyTarget =
  !rawApiUrl || rawApiUrl === '.' ? 'http://localhost:8080' : rawApiUrl.replace(/\/+$/, '');

/**
 * Resolve the application version from environment or VERSION file.
 *
 * Priority:
 *   1. VERSION env var (set by Docker build arg or manual export)
 *   2. VERSION file in the build working directory (Docker build stage)
 *   3. VERSION file at repo root (local development)
 *   4. Fallback to "dev"
 */
function getVersion(): string {
  const envVersion = process.env.VERSION;
  if (envVersion && envVersion !== 'dev') {
    return envVersion;
  }

  const candidates = [
    resolve(__dirname, 'VERSION'), // Docker build: VERSION copied into WORKDIR
    resolve(__dirname, '..', '..', 'VERSION'), // Local dev: repo root
  ];

  for (const candidate of candidates) {
    try {
      const content = readFileSync(candidate, 'utf-8').trim();
      if (/^\d+\.\d+\.\d+/.test(content)) {
        return content;
      }
    } catch {
      // File not found or unreadable — try next candidate
    }
  }

  return envVersion || 'dev';
}

// https://vitejs.dev/config/
export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(getVersion()),
  },
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
