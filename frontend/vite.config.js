import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { VitePWA } from 'vite-plugin-pwa'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    svelte(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['logos_192.png', 'logos_512.png', 'logos_miskable.png'],
      devOptions: {
        enabled: true,
        navigateFallback: '/',
        suppressWarnings: true
      },
      manifest: {
        name: 'Gemini DE Tutor',
        short_name: 'DE Tutor',
        description: 'German AI Language Tutor - Learn German with AI-powered lessons',
        theme_color: '#1976D2',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait-primary',
        scope: '/',
        start_url: '/',
        categories: ['education', 'productivity'],
        icons: [
          {
            src: 'logos_192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: 'logos_512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: 'logos_miskable.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable'
          }
        ],
        screenshots: [
          {
            src: 'logos_512.png',
            sizes: '512x512',
            type: 'image/png',
            form_factor: 'wide'
          }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^\/api\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 }
            }
          }
        ]
      }
    })
  ],
  server: {
    allowedHosts: ['german.vicolores.com'],
    middlewareMode: false,
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
  },
  preview: {
    allowedHosts: ['german.vicolores.com']
  }
})