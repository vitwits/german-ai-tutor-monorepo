<script>
  import { onMount } from "svelte";
  import api from "../lib/api";
  import { router } from "tinro";
  import { user } from "../stores/auth";
  import { getUI } from "../lib/ui";
  import { confirmModal } from "../stores/confirm";

  let texts = [];
  let page = 1;
  let totalPages = 1;
  let loading = false;
  
  // Filters
  let showFav = false;
  let selectedLevels = [];
  const allLevels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

  $: ui = getUI($user?.interface_language || 'ukr');

  async function loadLibrary() {
    loading = true;
    try {
      const params = {
        page,
        fav: showFav ? 1 : 0,
        levels: selectedLevels.join(',')
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
        selectedLevels = selectedLevels.filter(l => l !== lvl);
    } else {
        selectedLevels = [...selectedLevels, lvl];
    }
    page = 1;
    loadLibrary();
  }

  function toggleFavFilter() {
      showFav = !showFav;
      page = 1;
      loadLibrary();
  }

  function changePage(newPage) {
      if (newPage >= 1 && newPage <= totalPages) {
          page = newPage;
          loadLibrary();
      }
  }

  async function deleteText(id) {      
      const ok = await confirmModal.ask(ui.confirm_title, ui.confirm_delete_text_msg, ui.btn_delete, ui.btn_cancel, true);
      if (!ok) return;
      try {
          await api.post("/delete_text", { id });
          loadLibrary();
      } catch(e) { console.error(e); }
  }

  async function toggleFav(text) {
      // Optimistic update
      text.is_favorite = text.is_favorite ? 0 : 1;
      texts = texts; 
      try {
          await api.post("/toggle_text_fav", { id: text.id });
      } catch(e) { console.error(e); }
  }

  onMount(loadLibrary);
</script>

<div class="library-header">
    <h2 style="margin: 0;">{ui.my_texts}</h2>
    <div class="filters">
        <button class="icon-btn {showFav ? 'active-fav' : ''}" on:click={toggleFavFilter}>
            <span class="material-symbols-outlined {showFav ? 'filled' : ''}">favorite</span>
        </button>
        
        <div class="level-filters">
            {#each allLevels as lvl}
                <button class="lvl-filter {selectedLevels.includes(lvl) ? 'active' : ''}" 
                        on:click={() => toggleLevel(lvl)}
                        data-lvl={lvl}>
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
                    <span class="level-badge lvl-{t.level.toLowerCase()}">{t.level}</span>
                    <button class="btn-text fav-btn" on:click={() => toggleFav(t)}>
                        <span class="material-symbols-outlined {t.is_favorite ? 'filled' : ''}">favorite</span>
                    </button>
                </div>
                <div class="text-title">
                    {t.display_title}
                    {#if t.trans_title}
                        <div class="text-subtitle">{t.trans_title}</div>
                    {/if}
                </div>
            </div>
            <div class="card-actions">
                <!-- Link to View page (stub for now) -->
                <a href={`/view/${t.id}`} on:click|preventDefault={() => router.goto(`/view/${t.id}`)} class="btn-contained">{ui.read}</a>
                <button class="btn-text delete-btn" on:click={() => deleteText(t.id)}>
                    <span class="material-symbols-outlined">delete</span>
                </button>
            </div>
        </div>
    {/each}
</div>

{#if totalPages > 1}
<div class="pagination">
    <button class="page-btn" disabled={page===1} on:click={() => changePage(page-1)}>&lt;</button>
    <span>{page} / {totalPages}</span>
    <button class="page-btn" disabled={page===totalPages} on:click={() => changePage(page+1)}>&gt;</button>
</div>
{/if}

<style>
    .library-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .filters { display: flex; gap: 12px; align-items: center; }
    .level-filters { display: flex; gap: 4px; }
    
    /* minmax(320px, 1fr) гарантує 3 колонки на ширині 1200px (3 * 320 + відступи < 1200) */
    .texts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
    .text-card { height: 200px; display: flex; flex-direction: column; justify-content: space-between; margin-bottom: 0; }
    .text-title { font-weight: 500; font-size: 1.1rem; margin-top: 10px; }
    .text-subtitle { font-size: 0.9rem; opacity: 0.7; font-weight: 400; margin-top: 2px; }
    .card-actions { display: flex; justify-content: space-between; margin-top: auto; }
    
    .icon-btn { width: 36px; height: 36px; border: 1px solid var(--border); background: transparent; border-radius: var(--radius); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--on-surface); }
    .active-fav { border-color: #d32f2f; color: #d32f2f; background: rgba(211, 47, 47, 0.1); }
    
    .lvl-filter { width: 32px; height: 32px; border: 1px solid var(--border); background: var(--surface); border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.8rem; opacity: 0.6; }
    .lvl-filter.active { opacity: 1; color: white; border-color: transparent; }
    .lvl-filter.active[data-lvl="A1"] { background-color: #8BC34A; }
    .lvl-filter.active[data-lvl="A2"] { background-color: #4CAF50; }
    .lvl-filter.active[data-lvl="B1"] { background-color: #29B6F6; }
    .lvl-filter.active[data-lvl="B2"] { background-color: #1976D2; }
    .lvl-filter.active[data-lvl="C1"] { background-color: #D32F2F; }
    .lvl-filter.active[data-lvl="C2"] { background-color: #311B92; }

    .level-badge { padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; color: white; }
    .lvl-a1 { background-color: #8BC34A; } .lvl-a2 { background-color: #4CAF50; }
    .lvl-b1 { background-color: #29B6F6; } .lvl-b2 { background-color: #1976D2; }
    .lvl-c1 { background-color: #D32F2F; } .lvl-c2 { background-color: #311B92; }

    .fav-btn { padding: 0; min-width: 32px; }
    .fav-btn span.filled { color: #d32f2f; font-variation-settings: 'FILL' 1; }
    .delete-btn { color: #d32f2f; min-width: 32px; padding: 0; }

    .pagination { display: flex; justify-content: center; gap: 10px; margin-top: 20px; align-items: center; }
    .page-btn { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; background: var(--primary); color: white; border: none; border-radius: 6px; cursor: pointer; }
    .page-btn:disabled { opacity: 0.3; cursor: default; }
</style>