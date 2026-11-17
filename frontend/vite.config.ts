/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The built app is served by Django (WhiteNoise) from the same origin as the API.
// In development, Vite proxies API calls to the Django dev server.
const backend = process.env.BACKEND_URL ?? 'http://localhost:8000';
// The local browser talks to Vite on one port and Django on another. Forward the
// backend origin for these same-machine proxy requests; CSRF tokens remain required.
const apiProxy = {
  target: backend,
  changeOrigin: true,
  headers: { Origin: new URL(backend).origin },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': apiProxy,
      '/platform/api': apiProxy,
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
  test: {
    // Limit simultaneous jsdom startup so lazy-page tests stay responsive on Windows.
    maxWorkers: 2,
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
});
