import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [svelte()],
  server: {
    allowedHosts: ['german.vicolores.com'],
    proxy: {
      '/api': {
        // У Docker мережі звертаємось до сервісу за іменем 'backend'
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://backend:8000',
        changeOrigin: true,
      }
    },
    host: '0.0.0.0',
    port: 5173,
    watch: {
      // Використовуємо polling, якщо файлова система не прокидає події (важливо для Docker)
      usePolling: true,
    }
  }
})