<script>
  import { user } from "../stores/auth";
  import api from "../lib/api";
  import { router } from "tinro";

  let topic = "";
  let style = "neutral";
  let size = "M";
  let loading = false;

    async function handleSubmit() {
    if (!$user) {
        router.goto('/login');
        return;
    }
    loading = true;
    try {
      const res = await api.post("/generate", {
        topic,
        level: $user.level, // Беремо рівень з профілю юзера
        style,
        size
      });
      
      // ЯКЩО УСПІХ -> ЙДЕМО ЧИТАТИ
      if (res.data.id) {
          router.goto(`/view/${res.data.id}`); 
      }
    } catch (e) {
      console.error(e);
      alert("Error generating text: " + (e.response?.data?.detail || e.message));
    } finally {
      loading = false;
    }
  }

</script>

<form class="card form-container" on:submit|preventDefault={handleSubmit}>
    <div class="header-section">
        <span class="material-symbols-outlined header-icon">auto_stories</span>
        <h2 style="margin: 0; color: var(--primary); font-weight: 500; letter-spacing: 1px;">СТВОРИТИ УРОК</h2>
    </div>

    <div class="form-group">
        <label class="form-label" for="topic">Тема уроку</label>
        <!-- svelte-ignore a11y-autofocus -->
        <input type="text" id="topic" bind:value={topic} class="form-control control-height" placeholder="Наприклад: Подорож, IT, Спорт..." required autofocus>
    </div>

    <div class="controls-row">
        <div class="form-group" style="flex: 1;">
            <label class="form-label" for="style">Стиль тексту</label>
            <select id="style" bind:value={style} class="form-control control-height">
                <option value="neutral">Нейтральний</option>
                <option value="formal">Офіційний</option>
                <option value="conversational">Розмовний</option>
                <option value="dialogue_informal">Неформальний діалог</option>
                <option value="dialogue_formal">Офіційний діалог</option>
            </select>
        </div>
        <div class="form-group">
            <span class="form-label">Кількість речень</span>
            <div class="size-selector">
                {#each ['S', 'M', 'L'] as s}
                    <button type="button" class:active={size === s} on:click={() => size = s}>{s}</button>
                {/each}
            </div>
        </div>
    </div>

    <button type="submit" class="btn-contained" style="width: 100%; height: 50px; justify-content: center; font-size: 1rem; margin-top: 20px;" disabled={loading}>
        {#if loading}
            <span class="material-symbols-outlined rotating">sync</span> Генерація...
        {:else}
            <span class="material-symbols-outlined">auto_awesome</span> Згенерувати
        {/if}
    </button>
</form>

<style>
    .form-container { max-width: 500px; margin: 40px auto; padding: 40px; text-align: center; }
    .header-section { margin-bottom: 30px; }
    .header-icon { font-size: 48px; color: var(--primary); margin-bottom: 10px; }
    
    .controls-row { display: flex; align-items: flex-end; gap: 20px; }
    
    /* Size Selector Styles matching original */
    .size-selector { display: flex; gap: 8px; }
    .size-selector button {
        width: 45px; height: 45px;
        border: 1px solid var(--border); border-radius: var(--radius);
        background: var(--bg); color: var(--on-surface);
        cursor: pointer; font-weight: 500;
        display: flex; align-items: center; justify-content: center;
        padding: 0; transition: all 0.2s;
    }
    .size-selector button.active {
        background: var(--primary); color: white; border-color: var(--primary);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .size-selector button:hover { border-color: var(--primary); }

    .rotating { animation: rotate 1.5s linear infinite; margin-right: 8px; }
    @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    
    .btn-contained:disabled { opacity: 0.7; cursor: not-allowed; }
</style>