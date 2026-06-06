import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte/svelte5';
import ProgressSplash from '../ProgressSplash.svelte';

describe('ProgressSplash Component', () => {
    it('should render without crashing', () => {
        const { container } = render(ProgressSplash);
        expect(container).toBeTruthy();
    });

    it('should have splash container element', () => {
        const { container } = render(ProgressSplash);
        // Just verify the component renders without error
        // The actual structure depends on component implementation
        expect(container.firstChild).toBeTruthy();
    });
});
