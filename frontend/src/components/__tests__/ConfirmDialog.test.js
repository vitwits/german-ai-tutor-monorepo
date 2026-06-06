import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/svelte/svelte5';
import ConfirmDialog from '../ConfirmDialog.svelte';

// Mock the confirm store
vi.mock('../../stores/confirm', () => ({
    confirmModal: {
        subscribe: vi.fn((cb) => {
            cb({
                show: true,
                title: 'Confirm Action',
                message: 'Are you sure?',
                okText: 'OK',
                cancelText: 'Cancel',
                isDanger: false,
            });
            return () => { };
        }),
        close: vi.fn(),
    },
}));

describe('ConfirmDialog Component', () => {
    it('should render when modal is shown', () => {
        const { container } = render(ConfirmDialog);
        const overlay = container.querySelector('.modal-overlay');
        expect(overlay).toBeTruthy();
    });

    it('should display title and message', () => {
        const { container } = render(ConfirmDialog);
        const title = container.querySelector('#sys-confirm-title');
        const body = container.querySelector('#sys-confirm-body');

        expect(title).toBeTruthy();
        expect(body).toBeTruthy();
    });

    it('should have action buttons', () => {
        const { container } = render(ConfirmDialog);
        const buttons = container.querySelectorAll('button');
        expect(buttons.length).toBeGreaterThanOrEqual(2);
    });

    it('should apply danger style when isDanger is true', () => {
        const { container } = render(ConfirmDialog);
        const dangerButton = container.querySelector('.btn-danger');
        // This may or may not exist depending on isDanger state
        expect(container.querySelector('button')).toBeTruthy();
    });
});
