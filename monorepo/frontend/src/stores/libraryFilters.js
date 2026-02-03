import { writable } from 'svelte/store';

// Зберігаємо фільтри Library в localStorage
function createLibraryFilters() {
    // Спробуємо завантажити з localStorage
    const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('libraryFilters') : null;
    const initial = stored ? JSON.parse(stored) : {
        showFav: false,
        selectedLevels: [],
        sortBy: 'date_desc' // date_desc, date_asc
    };

    const { subscribe, set, update } = writable(initial);

    return {
        subscribe,
        setShowFav: (value) => update(f => ({ ...f, showFav: value })),
        setSelectedLevels: (levels) => update(f => ({ ...f, selectedLevels: levels })),
        setSortBy: (sortBy) => update(f => ({ ...f, sortBy })),
        reset: () => {
            const initial = { showFav: false, selectedLevels: [], sortBy: 'date_desc' };
            set(initial);
            if (typeof localStorage !== 'undefined') {
                localStorage.removeItem('libraryFilters');
            }
        },
        save: (filters) => {
            set(filters);
            if (typeof localStorage !== 'undefined') {
                localStorage.setItem('libraryFilters', JSON.stringify(filters));
            }
        }
    };
}

export const libraryFilters = createLibraryFilters();
