<script>
  import { router } from "tinro"; // Ensure this is correct
  import { user, isAuthenticated, logout } from "../stores/auth";
  import api from "../lib/api";

  let showMenu = false;
  let isDark = localStorage.getItem('t') === 'd';

  // Ініціалізація теми при завантаженні
  if (isDark) document.body.classList.add('dark-mode');

  function toggleTheme() {
    isDark = !isDark;
    if (isDark) {
      document.body.classList.add('dark-mode');
      localStorage.setItem('t', 'd');
    } else {
      document.body.classList.remove('dark-mode');
      localStorage.setItem('t', 'l');
    }
  }

  async function updateLevel(lvl) {
    if (!$user) return;
    try {
      await api.post('/auth/update_level', { level: lvl });
      // Оновлюємо локальний стор
      user.update(u => ({ ...u, level: lvl }));
      // Відправляємо подію, щоб інші компоненти (наприклад Speaking) могли оновитися
      window.dispatchEvent(new CustomEvent('level-updated'));
    } catch (e) {
      console.error(e);
    }
  }

  const levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
</script>

<div class="header">
  <a href="/" class="brand" on:click|preventDefault={() => router.goto('/')}>
    <span class="material-symbols-outlined" style="color:var(--primary)">school</span>
    Gemini <span class="brand-de">DE</span>
  </a>

  <div class="header-right">
    {#if $isAuthenticated}
      <div class="credits-pill" title="Credits">
        <span>💎</span> 
        <span id="user-credits">{$user ? Math.floor($user.credits) : '...'}</span> 
        <span style="opacity:0.5; font-size:0.75rem;">/ 1000</span>
      </div>

      <div class="level-tiles">
        {#each levels as lvl}
          <button 
            class="lvl-tile lvl-{lvl.toLowerCase()} { ($user && $user.level === lvl) ? 'active' : '' }"
            on:click={() => updateLevel(lvl)}
          >
            {lvl}
          </button>
        {/each}
      </div>
    {/if}

    <button class="btn-text" on:click={toggleTheme}>
      <span class="material-symbols-outlined">{isDark ? 'light_mode' : 'dark_mode'}</span>
    </button>

    {#if $isAuthenticated}
      <div style="position: relative;">
        <button class="btn-text settings-trigger" on:click={() => showMenu = !showMenu}>
          <span class="material-symbols-outlined">settings</span>
        </button>
        {#if showMenu}
          <div class="dropdown-menu">
            <button class="dropdown-item" on:click={() => { showMenu = false; router.goto('/settings'); }}>
              <span class="material-symbols-outlined" style="font-size: 20px;">tune</span> Налаштування
            </button>
            <button class="dropdown-item" on:click={() => { showMenu = false; logout(); }}>
              <span class="material-symbols-outlined" style="font-size: 20px;">logout</span> Вийти
            </button>
          </div>
          <!-- Backdrop to close menu -->
          <div class="menu-backdrop" 
               on:click={() => showMenu = false}
               on:keydown={(e) => e.key === 'Escape' && (showMenu = false)}
               role="button"
               tabindex="0"
               aria-label="Close menu"></div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .header { display: flex; justify-content: space-between; align-items: center; background: var(--surface); padding: 16px 24px; box-shadow: var(--shadow); margin-bottom: 24px; }
  .brand { font-size: 1.5rem; font-weight: 500; display: flex; align-items: center; gap: 8px; text-transform: uppercase; text-decoration: none; color: var(--on-surface); }
  .brand-de { color: var(--primary); font-weight: 700; }
  .header-right { display: flex; align-items: center; gap: 8px; }

  .credits-pill {
    background: rgba(0,0,0,0.05); border: 1px solid var(--border);
    padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 500;
    display: flex; align-items: center; gap: 6px; color: var(--on-surface);
    margin-right: 12px;
  }

  .level-tiles { display: flex; gap: 4px; margin-right: 12px; }
  
  /* Стилі lvl-tile вже є в app.css, але Svelte ізолює стилі, тому дублюємо або використовуємо :global */
  /* Для надійності тут локальні, але ідентичні глобальним */
  .lvl-tile {
    width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
    border-radius: 4px; font-size: 0.75rem; font-weight: 700; cursor: pointer; color: white;
    opacity: 0.3; transition: all 0.2s; border: none; padding: 0;
  }
  .lvl-tile:hover { opacity: 0.7; transform: translateY(-1px); }
  .lvl-tile.active { opacity: 1; transform: scale(1.1); box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
  
  .lvl-a1 { background-color: #8BC34A; } .lvl-a2 { background-color: #4CAF50; }
  .lvl-b1 { background-color: #29B6F6; } .lvl-b2 { background-color: #1976D2; }
  .lvl-c1 { background-color: #D32F2F; } .lvl-c2 { background-color: #311B92; }

  .dropdown-menu {
    position: absolute; right: 0; top: 100%; background: var(--surface);
    border: 1px solid var(--border); border-radius: var(--radius);
    box-shadow: var(--shadow); min-width: 160px; z-index: 1001; margin-top: 4px;
  }
  .dropdown-item {
    display: flex; align-items: center; gap: 12px; padding: 12px 16px; width: 100%;
    text-align: left; background: none; border: none; color: var(--on-surface);
    font-size: 0.9rem; cursor: pointer;
  }
  .dropdown-item:hover { background-color: rgba(0,0,0,0.05); }
  .menu-backdrop { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 1000; }
</style>
