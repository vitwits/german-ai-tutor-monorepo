import { describe, it, expect } from 'vitest';

// Example utility function tests
describe('Basic Tests', () => {
    it('should pass basic equality check', () => {
        expect(1 + 1).toBe(2);
    });

    it('should check string matching', () => {
        const message = 'Hello Svelte';
        expect(message).toContain('Svelte');
    });

    it('should work with arrays', () => {
        const arr = [1, 2, 3, 4, 5];
        expect(arr).toHaveLength(5);
        expect(arr).toContain(3);
    });

    it('should work with objects', () => {
        const user = { name: 'John', level: 'A1' };
        expect(user).toEqual({ name: 'John', level: 'A1' });
        expect(user.level).toBe('A1');
    });
});
