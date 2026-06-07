import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
    plugins: [svelte()],
    server: {
        hmr: false,
    },
    resolve: {
        // Це критично для Svelte 5: змушує Vitest використовувати браузерні версії бібліотек
        conditions: ['browser', 'svelte']
    },
    test: {
        globals: true,
        environment: 'jsdom',
        alias: {
            'svelte': 'svelte/index.js'
        },
        coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html'],
        },
    },
});
