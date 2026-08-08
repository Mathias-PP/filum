import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      // Certains défauts ne se voient qu'au navigateur, sur une vraie fiche —
      // le thème du graphe en est un. Monter Postgres et le backend pour cela
      // seul est disproportionné : `API_PROXY_TARGET=https://philum-api.duckdns.org`
      // suffit à regarder l'interface locale sur les données de production.
      '/api': {
        target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'esnext',
    minify: 'esbuild',
  },
  optimizeDeps: {
    include: ['d3'],
  },
});
