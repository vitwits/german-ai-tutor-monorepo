<script>
    /* eslint-disable */
    import { onMount } from "svelte";
    import api from "../lib/api";
    import { router } from "tinro";
    import { user } from "../stores/auth";
    import { libraryFilters } from "../stores/libraryFilters";
    import { getUI } from "../lib/ui";
    import { confirmModal } from "../stores/confirm";
    import { addToast } from "../stores/toast";

    let texts = [];
    let page = 1;
    let totalPages = 1;
    let loading = false;

    // Filters - підписуємось на store
    let showFav = false;
    let selectedLevels = [];
    let sortBy = "date_desc";
    let searchQuery = "";
    const allLevels = ["A1", "A2", "B1", "B2", "C1", "C2"];

    let searchTimeout;

    // Підписуємось на зміни фільтрів
    const unsubscribeFilters = libraryFilters.subscribe((filters) => {
        showFav = filters.showFav;
        selectedLevels = filters.selectedLevels;
        sortBy = filters.sortBy;
    });

    onMount(() => {
        loadLibrary();
        return unsubscribeFilters;
    });

    function onSearchChange() {
        clearTimeout(searchTimeout);
        page = 1; // Reset to first page when searching
        searchTimeout = setTimeout(loadLibrary, 300); // Debounce search
    }

    $: ui = getUI($user?.interface_language || "ukr");

    async function loadLibrary() {
        loading = true;
        try {
            const params = {
                page,
                fav: showFav ? 1 : 0,
                levels: selectedLevels.join(","),
                search: searchQuery,
                sort: sortBy,
            };
            const res = await api.get("/library", { params });
            texts = res.data.texts;
            totalPages = res.data.total_pages;
        } catch (e) {
            console.error(e);
        } finally {
            loading = false;
        }
    }

    function toggleLevel(lvl) {
        if (selectedLevels.includes(lvl)) {
            selectedLevels = selectedLevels.filter((l) => l !== lvl);
        } else {
            selectedLevels = [...selectedLevels, lvl];
        }
        page = 1;
        libraryFilters.setSelectedLevels(selectedLevels);
        loadLibrary();
    }

    function toggleFavFilter() {
        showFav = !showFav;
        page = 1;
        libraryFilters.setShowFav(showFav);
        loadLibrary();
    }

    function changePage(newPage) {
        if (newPage >= 1 && newPage <= totalPages) {
            page = newPage;
            loadLibrary();
        }
    }

    async function deleteText(id) {
        const ok = await confirmModal.ask(
            ui.confirm_title,
            ui.confirm_delete_text_msg,
            ui.btn_delete,
            ui.btn_cancel,
            true,
        );
        if (!ok) return;

        // Proceed with deletion + undo toast
        const originalTexts = [...texts];
        texts = texts.filter((t) => t.id !== id); // Optimistic UI

        // Delayed actual delete
        const deleteTimeout = setTimeout(() => {
            api.post("/delete_text", { id }).catch((e) => {
                console.error("Final delete failed:", e);
                addToast("Error deleting text", "error");
                texts = originalTexts; // Revert UI on error
            });
        }, 5000);

        // Show toast with undo action
        const undo = () => {
            clearTimeout(deleteTimeout);
            texts = originalTexts;
        };

        addToast(ui.text_deleted || "Text deleted", "info", undo, 5000);
    }

    async function toggleFav(text) {
        // Optimistic update
        text.is_favorite = text.is_favorite ? 0 : 1;
        texts = texts;
        try {
            await api.post("/toggle_text_fav", { id: text.id });
        } catch (e) {
            console.error(e);
        }
    }

    // Mobile: search narrows to make room for the level chips; tapping it
    // expands the search to full width and temporarily hides the levels.
    let searchFocused = false;

    let editingTitleId = null;
    let editTitleValue = "";

    function startTitleEdit(e, t) {
        e.stopPropagation();
        editTitleValue = t.display_title;
        editingTitleId = t.id;
    }

    function cancelTitleEdit() {
        editingTitleId = null;
        editTitleValue = "";
    }

    async function saveTitleEdit(id) {
        const trimmed = editTitleValue.trim().slice(0, 60);
        if (!trimmed) return;
        try {
            await api.post("/rename_text", { id, title: trimmed });
            texts = texts.map((t) =>
                t.id === id ? { ...t, display_title: trimmed } : t,
            );
            editingTitleId = null;
        } catch (e) {
            console.error(e);
            addToast("Error renaming", "error");
        }
    }
</script>

<div class="library-header" class:search-active={searchFocused}>
    <div class="search-wrap">
        <span class="material-symbols-outlined search-icon">search</span>
        <input
            type="text"
            class="search-input"
            placeholder={ui.search || "Search..."}
            bind:value={searchQuery}
            oninput={onSearchChange}
            onfocus={() => (searchFocused = true)}
            onblur={() => {
                searchFocused = false;
                searchQuery = "";
                loadLibrary();
            }}
        />
    </div>
    <div class="filters">
        <button
            class="icon-btn {showFav ? 'active-fav' : ''}"
            onclick={toggleFavFilter}
        >
            <span class="material-symbols-outlined {showFav ? 'filled' : ''}"
                >favorite</span
            >
        </button>

        <div class="level-filters">
            {#each allLevels as lvl}
                <button
                    class="lvl-filter {selectedLevels.includes(lvl)
                        ? 'active'
                        : ''}"
                    onclick={() => toggleLevel(lvl)}
                    data-lvl={lvl}
                >
                    {lvl}
                </button>
            {/each}
        </div>
    </div>
</div>

<div class="texts-grid">
    {#each texts as t (t.id)}
        <div class="card text-card">
            <div class="card-top">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="level-badge lvl-{t.level.toLowerCase()}"
                        >{t.level}</span
                    >
                    <button
                        class="btn-text fav-btn"
                        onclick={() => toggleFav(t)}
                    >
                        <span
                            class="material-symbols-outlined {t.is_favorite
                                ? 'filled'
                                : ''}">favorite</span
                        >
                    </button>
                </div>
                <div class="text-title-row">
                    {#if editingTitleId === t.id}
                        <input
                            type="text"
                            class="edit-title-input"
                            bind:value={editTitleValue}
                            maxlength="60"
                            onclick={(e) => e.stopPropagation()}
                            onkeydown={(e) => {
                                e.stopPropagation();
                                if (e.key === "Enter") saveTitleEdit(t.id);
                                if (e.key === "Escape") cancelTitleEdit();
                            }}
                        />
                        <button
                            class="btn-text"
                            onclick={(e) => {
                                e.stopPropagation();
                                saveTitleEdit(t.id);
                            }}
                            style="padding:0; min-width:28px;"
                        >
                            <span
                                class="material-symbols-outlined"
                                style="font-size:18px;">check</span
                            >
                        </button>
                        <button
                            class="btn-text"
                            onclick={(e) => {
                                e.stopPropagation();
                                cancelTitleEdit();
                            }}
                            style="padding:0; min-width:28px;"
                        >
                            <span
                                class="material-symbols-outlined"
                                style="font-size:18px;">close</span
                            >
                        </button>
                    {:else}
                        <div class="text-title">{t.display_title}</div>
                        <button
                            class="btn-text rename-btn"
                            onclick={(e) => startTitleEdit(e, t)}
                            title="Rename"
                        >
                            <span
                                class="material-symbols-outlined"
                                style="font-size:16px;">edit</span
                            >
                        </button>
                    {/if}
                </div>
            </div>
            <div class="card-actions">
                <!-- Link to View page (stub for now) -->
                <button
                    type="button"
                    onclick={() => router.goto(`/view/${t.id}`)}
                    class="btn-contained">{ui.read}</button
                >
                <button
                    class="btn-text delete-btn"
                    onclick={(e) => {
                        e.stopPropagation();
                        deleteText(t.id);
                    }}
                >
                    <span class="material-symbols-outlined">delete</span>
                </button>
            </div>
        </div>
    {/each}
</div>

{#if totalPages > 1}
    <div class="pagination">
        <button
            class="page-btn"
            disabled={page === 1}
            onclick={() => changePage(page - 1)}>&lt;</button
        >
        <span>{page} / {totalPages}</span>
        <button
            class="page-btn"
            disabled={page === totalPages}
            onclick={() => changePage(page + 1)}>&gt;</button
        >
    </div>
{/if}

<style>
    .library-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    .filters {
        display: flex;
        gap: 12px;
        align-items: center;
    }
    .level-filters {
        display: flex;
        gap: 4px;
    }

    .search-input {
        padding: 8px 12px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--surface);
        color: var(--on-surface);
        font-size: 0.95rem;
        min-width: 200px;
    }
    .search-input::placeholder {
        opacity: 0.5;
    }
    .search-wrap {
        position: relative;
    }
    .search-icon {
        display: none;
    }

    /* minmax(320px, 1fr) гарантує 3 колонки на ширині 1200px (3 * 320 + відступи < 1200) */
    .texts-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 20px;
    }
    .text-card {
        height: 176px;
        padding: 24px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        margin-bottom: 0;
        border: 1px solid var(--border);
        min-width: 0;
    }
    .card-top {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-height: 0;
    }
    .text-title {
        font-weight: 500;
        font-size: 1.1rem;
        min-width: 0;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }
    .text-title-row {
        display: flex;
        align-items: center;
        gap: 4px;
        flex: 1;
        min-width: 0;
    }
    .rename-btn {
        opacity: 0;
        padding: 0;
        min-width: 24px;
        height: 24px;
        transition: opacity 0.15s;
        color: var(--on-surface);
    }
    .card-top:hover .rename-btn {
        opacity: 0.45;
    }
    .rename-btn:hover {
        opacity: 1 !important;
    }
    .edit-title-input {
        flex: 1;
        min-width: 0;
        border: none;
        border-bottom: 1px solid var(--primary);
        background: transparent;
        color: var(--on-surface);
        font-size: 1.05rem;
        font-weight: 500;
        font-family: inherit;
        outline: none;
        padding: 0;
        margin-top: 10px;
    }
    .text-subtitle {
        font-size: 0.9rem;
        opacity: 0.7;
        font-weight: 400;
        margin-top: 2px;
    }
    .card-actions {
        display: flex;
        justify-content: space-between;
        margin-top: auto;
    }

    .icon-btn {
        width: 36px;
        height: 36px;
        border: 1px solid var(--border);
        background: transparent;
        border-radius: var(--radius);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        color: var(--on-surface);
    }
    .active-fav {
        border-color: #d32f2f;
        color: #d32f2f;
        background: rgba(211, 47, 47, 0.1);
    }

    .lvl-filter {
        width: 32px;
        height: 32px;
        border: 1px solid var(--border);
        background: var(--surface);
        border-radius: 6px;
        cursor: pointer;
        font-weight: 600;
        font-size: 0.8rem;
        opacity: 0.6;
        color: var(--on-surface);
    }
    .lvl-filter.active {
        opacity: 1;
        color: white;
        border-color: transparent;
    }
    .lvl-filter.active[data-lvl="A1"] {
        background-color: #8bc34a;
    }
    .lvl-filter.active[data-lvl="A2"] {
        background-color: #4caf50;
    }
    .lvl-filter.active[data-lvl="B1"] {
        background-color: #29b6f6;
    }
    .lvl-filter.active[data-lvl="B2"] {
        background-color: #1976d2;
    }
    .lvl-filter.active[data-lvl="C1"] {
        background-color: #d32f2f;
    }
    .lvl-filter.active[data-lvl="C2"] {
        background-color: #311b92;
    }

    .level-badge {
        padding: 2px 2px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 700;
        color: white;
    }
    .lvl-a1 {
        background-color: #8bc34a;
    }
    .lvl-a2 {
        background-color: #4caf50;
    }
    .lvl-b1 {
        background-color: #29b6f6;
    }
    .lvl-b2 {
        background-color: #1976d2;
    }
    .lvl-c1 {
        background-color: #d32f2f;
    }
    .lvl-c2 {
        background-color: #311b92;
    }

    .fav-btn {
        padding: 0;
        min-width: 32px;
    }
    .fav-btn span.filled {
        color: #d32f2f;
        font-variation-settings: "FILL" 1;
    }
    .delete-btn {
        color: #d32f2f;
        min-width: 32px;
        padding: 0;
    }

    .pagination {
        display: flex;
        justify-content: center;
        gap: 10px;
        margin-top: 20px;
        align-items: center;
    }
    .page-btn {
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--primary);
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
    }
    .page-btn:disabled {
        opacity: 0.3;
        cursor: default;
    }

    /*
     * Mobile (< 1024px, minimum tested size iPhone X 375x812):
     * the search box collapses to a square search-icon button so the
     * (bigger, square) level chips + favorite filter fit on one row;
     * tapping/focusing the search expands it to full width and hides
     * the level chips temporarily.
     */
    @media (max-width: 1023px) {
        .library-header {
            flex-wrap: nowrap;
            gap: 4px;
            --row-h: 40px;
        }

        .search-wrap {
            position: relative;
            display: flex;
            align-items: center;
            flex: 0 0 var(--row-h);
            height: var(--row-h);
            transition: flex-basis 0.15s ease;
        }

        .library-header.search-active .search-wrap {
            flex: 1 1 auto;
        }

        .search-input {
            width: 100%;
            height: var(--row-h);
            min-width: 0;
            box-sizing: border-box;
        }

        .library-header:not(.search-active) .search-input {
            padding: 0;
            text-align: center;
            cursor: pointer;
        }

        .library-header:not(.search-active) .search-input::placeholder {
            color: transparent;
        }

        .search-icon {
            display: flex;
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            pointer-events: none;
            font-size: 20px;
            opacity: 0.6;
        }

        .library-header.search-active .search-icon {
            display: none;
        }

        .filters {
            gap: 4px;
            flex-shrink: 0;
        }

        .level-filters {
            gap: 4px;
        }

        .lvl-filter {
            width: var(--row-h);
            height: var(--row-h);
            font-size: 0.8rem;
        }

        .icon-btn {
            width: var(--row-h);
            height: var(--row-h);
            flex-shrink: 0;
        }

        .library-header.search-active .level-filters {
            display: none;
        }

        .texts-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
