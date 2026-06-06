module.exports = {
    root: true,
    env: {
        browser: true,
        es2021: true,
        node: true,
    },
    extends: [
        'eslint:recommended',
        'plugin:svelte/recommended',
        'plugin:@typescript-eslint/recommended', // Add TypeScript recommended rules
    ],
    parserOptions: {
        ecmaVersion: 12,
        sourceType: 'module',
        parser: '@typescript-eslint/parser', // Use TypeScript parser
    },
    plugins: [
        'svelte',
        '@typescript-eslint', // Add TypeScript plugin
    ],
    overrides: [
        {
            files: ['*.svelte'],
            parser: 'svelte-eslint-parser',
        },
    ],
    rules: {
        // Add your custom rules here
    },
};