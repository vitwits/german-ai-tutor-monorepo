import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render } from '@testing-library/svelte/svelte5';
import Toast from '../Toast.svelte';

// Mock the stores
vi.mock('../../stores/toast', () => ({
    toasts: {
        subscribe: vi.fn((cb) => {
            cb([{ id: 1, msg: 'Test message', type: 'success', duration: 3000 }]);
            return () => { };
        })
    },
    addToast: vi.fn(),
    removeToast: vi.fn(),
}));

vi.mock('../../lib/ui', () => ({
    getUI: vi.fn(() => ({ undo: 'UNDO' })),
}));

vi.mock('../../stores/auth', () => ({
    user: {
        subscribe: vi.fn((cb) => {
            cb({ interface_language: 'ukr' });
            return () => { };
        })
    },
}));

describe('Toast Component', () => {
    it('should render toast container', () => {
        const { container } = render(Toast);
        const toastContainer = container.querySelector('.toast-container');
        expect(toastContainer).toBeTruthy();
    });

    it('should display toast message and apply correct style classes', () => {
        const { container } = render(Toast);
        const toastElement = container.querySelector('.toast');
        expect(toastElement).toBeTruthy();
        expect(toastElement.classList.contains('success')).toBe(true);
        expect(container.textContent).toContain('Test message');
    });
});
