<script>
  import { user } from "../stores/auth";
  import api from "../lib/api";
  import { router } from "tinro";
  import { getUI } from "../lib/ui";
  import ProgressSplash from "../components/ProgressSplash.svelte";

  let topic = "";
  let customText = "";
  let mode = "topic"; // 'topic' або 'text'
  let style = "neutral";
  let size = "M";
  let loading = false;
  let showSplash = false;
  let generatedTextId = null;
  let apiArrived = false;

  $: ui = getUI($user?.interface_language || 'ukr');

  async function handleSubmit() {
    if (!$user) {
        router.goto('/login');
        return;
    }
    loading = true;
    showSplash = true;
    apiArrived = false;
    generatedTextId = null;

    try {
      const res = await api.post("/generate", {
        topic: mode === "topic" ? topic : customText,
        level: $user.level,
        style,
        size
      });
      
      if (res.data.id) {
        generatedTextId = res.data.id;
        apiArrived = true;
        // Splash екран автоматично перенаправить на /view/{id}
      }
    } catch (e) {
      console.error(e);
      showSplash = false;
      loading = false;
      alert("Error generating text: " + (e.response?.data?.detail || e.message));
    }
  }

</script>

<form class="card form-container" onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
    <div class="header-section">
        <span class="material-symbols-outlined header-icon">auto_stories</span>
        <h2 style="margin: 0; color: var(--primary); font-weight: 500; letter-spacing: 1px;">{ui.generate_new}</h2>
    </div>

    <!-- Mode Toggle Switch -->
    <div class="mode-toggle">
        <button
            type="button"
            class="toggle-btn"
            class:active={mode === 'topic'}
            onclick={() => mode = 'topic'}
            disabled={loading}
        >
            {ui.choose_topic}
        </button>
        <button
            type="button"
            class="toggle-btn"
            class:active={mode === 'text'}
            onclick={() => mode = 'text'}
            disabled={loading}
        >
            {ui.your_text}
        </button>
    </div>

    <!-- Topic Mode -->
    {#if mode === 'topic'}
        <div class="form-group">
            <label class="form-label" for="topic">{ui.topic}</label>
            <!-- svelte-ignore a11y-autofocus -->
            <input type="text" id="topic" bind:value={topic} class="form-control control-height" placeholder={ui.topic_placeholder} required autofocus disabled={loading}>
        </div>

        <div class="controls-row">
            <div class="form-group" style="flex: 1;">
                <label class="form-label" for="style">{ui.style_label}</label>
                <select id="style" bind:value={style} class="form-control control-height" disabled={loading}>
                    <option value="neutral">{ui.style_neutral}</option>
                    <option value="formal">{ui.style_formal}</option>
                    <option value="conversational">{ui.style_conversational}</option>
                    <option value="dialogue_informal">{ui.style_dialogue_informal}</option>
                    <option value="dialogue_formal">{ui.style_dialogue_formal}</option>
                </select>
            </div>
            <div class="form-group">
                <span class="form-label">{ui.count}</span>
                <div class="size-selector">
                    {#each ['S', 'M', 'L'] as s}
                        <button type="button" class:active={size === s} onclick={() => size = s} disabled={loading}>{s}</button>
                    {/each}
                </div>
            </div>
        </div>

        <button type="submit" class="btn-contained" style="width: 100%; height: 50px; justify-content: center; font-size: 1rem; margin-top: 20px;" disabled={loading}>
            {#if loading}
                <span class="material-symbols-outlined rotating">sync</span> {ui.generating}
            {:else}
                <span class="material-symbols-outlined">auto_awesome</span> {ui.generate_btn}
            {/if}
        </button>
    {/if}

    <!-- Text Mode -->
    {#if mode === 'text'}
        <div class="form-group">
            <label class="form-label" for="customText">{ui.your_german_text}</label>
            <textarea
                id="customText"
                bind:value={customText}
                class="form-control text-input"
                placeholder={ui.use_your_german_text}
                required
                disabled={loading}
                rows="10"
            ></textarea>
        </div>

        <button type="submit" class="btn-contained" style="width: 100%; height: 50px; justify-content: center; font-size: 1rem; margin-top: 20px;" disabled={loading}>
            {#if loading}
                <span class="material-symbols-outlined rotating">sync</span> {ui.generating}
            {:else}
                <span class="material-symbols-outlined">check_circle</span> {ui.create_btn}
            {/if}
        </button>
    {/if}
</form>

<ProgressSplash 
  isVisible={showSplash}
  userLanguage={$user?.interface_language || 'ukr'}
  apiArrived={apiArrived}
  textId={generatedTextId}
  userLevel={$user?.level || 'B1'}
/>

<style>
    .form-container { max-width: 500px; margin: 40px auto; padding: 40px; text-align: center; }
    .header-section { margin-bottom: 30px; }
    .header-icon { font-size: 48px; color: var(--primary); margin-bottom: 10px; }
    
    /* Mode Toggle Styles */
    .mode-toggle {
        display: flex;
        gap: 0;
        margin-bottom: 30px;
        border-radius: var(--radius);
        overflow: hidden;
        border: 1px solid var(--border);
        height: 50px;
    }
    
    .toggle-btn {
        flex: 1;
        border: none;
        background: var(--bg);
        color: var(--on-surface);
        cursor: pointer;
        font-weight: 500;
        font-size: 0.95rem;
        transition: all 0.2s ease;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
    }
    
    .toggle-btn:first-child {
        border-radius: var(--radius) 0 0 var(--radius);
    }
    
    .toggle-btn:last-child {
        border-radius: 0 var(--radius) var(--radius) 0;
    }
    
    .toggle-btn.active {
        background: var(--primary);
        color: var(--on-primary);
    }
    
    .toggle-btn.active:hover:not(:disabled) {
        background: var(--primary);
        color: var(--on-primary);
    }
    
    .toggle-btn:not(.active):hover:not(:disabled) {
        background: var(--surface);
        color: var(--on-surface);
    }
    
    .toggle-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
    
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

    /* Textarea styles for custom text mode */
    .text-input {
        resize: vertical;
        min-height: 150px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        line-height: 1.5;
        padding: 12px !important;
    }
    
    .text-input:focus {
        min-height: 150px;
    }

    .rotating { animation: rotate 1.5s linear infinite; margin-right: 8px; }
    @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    
    .btn-contained:disabled { opacity: 0.7; cursor: not-allowed; }
</style>