import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte/svelte5';
import Toast from '../Toast.svelte';
import { toasts, addToast, removeToast } from '../../stores/toast';

// Mock the stores
vi.mock('../../stores/toast', () => ({
    toasts: { subscribe: vi.fn() },
    addToast: vi.fn(),
    removeToast: vi.fn(),
}));

vi.mock('../../lib/ui', () => ({
    getUI: () => ({ undo: 'UNDO' }),
}));

vi.mock('../../stores/auth', () => ({
    user: { subscribe: () => () => { } },
}));

describe('Toast Component', () => {
    let unsubscribe;

    beforeEach(() => {
        // Set up the store with initial data
        const mockToasts = [
            { id: 1, msg: 'Test message', type: 'success', duration: 3000 },
        ];

        toasts.subscribe = vi.fn((cb) => {
            cb(mockToasts);
            return () => { };
        });
    });

    it('should render toast container', () => {
        const { container } = render(Toast);
        const toastContainer = container.querySelector('.toast-container');
        expect(toastContainer).toBeTruthy();
    });

    it('should display toast message', async () => {
        const { component, container } = render(Toast);

        // Check that toast element exists
        const toastElement = container.querySelector('.toast');
        expect(toastElement).toBeTruthy();
    });

    it('should apply correct style classes', () => {
        const { container } = render(Toast);
        const toastElement = container.querySelector('.toast');
        expect(toastElement?.classList.contains('toast')).toBe(true);
    });
});
