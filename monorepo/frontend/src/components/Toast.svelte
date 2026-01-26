<script>
  import { toasts, removeToast } from "../stores/toast";
  import { flip } from "svelte/animate";
  import { fade, fly } from "svelte/transition";
  import { getUI } from "../lib/ui";
  import { user } from "../stores/auth";

  $: ui = getUI($user?.interface_language || 'ukr');

  function handleUndo(toast) {
    if (toast.onUndo) {
      toast.onUndo();
    }
    removeToast(toast.id);
  }
</script>

<div class="toast-container">
  {#each $toasts as toast (toast.id)}
    <div class="toast {toast.type}" animate:flip={{duration: 200}} transition:fly={{ y: 20, duration: 300 }}>
      {#if toast.onUndo}
        <div class="toast-timer">
          <svg viewBox="0 0 20 20">
            <circle class="timer-progress" cx="10" cy="10" r="8" style="animation-duration: {toast.duration || 5000}ms;"></circle>
          </svg>
        </div>
      {/if}
      <span>{toast.msg}</span>
      {#if toast.onUndo}
        <button class="undo-btn" on:click={() => handleUndo(toast)}>{ui.undo || 'UNDO'}</button>
      {:else}
        <button class="close-btn" on:click={() => removeToast(toast.id)}>×</button>
      {/if}
    </div>
  {/each}
</div>

<style>
  .toast-container {
    position: fixed; top: 20px; right: 20px; z-index: 10000;
    display: flex; flex-direction: column; gap: 10px;
  }
  .toast {
    background: var(--surface); color: var(--on-surface);
    padding: 12px 16px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    display: flex; align-items: center; justify-content: flex-start; gap: 12px; min-width: 280px;
    border-left: 4px solid var(--primary); font-size: 0.9rem; font-weight: 500;
  }
  .toast.error { border-left-color: #d32f2f; }
  .toast.success { border-left-color: #4CAF50; }
  .close-btn { background: none; border: none; font-size: 1.2rem; cursor: pointer; padding: 0; color: inherit; opacity: 0.6; }

  .undo-btn {
    background: none;
    border: none;
    color: var(--primary);
    font-weight: 700;
    font-size: 0.8rem;
    cursor: pointer;
    text-transform: uppercase;
    padding: 4px 8px;
  }

  .toast-timer {
    width: 20px;
    height: 20px;
    position: relative;
    flex-shrink: 0;
  }
  .toast-timer svg {
    transform: rotate(-90deg);
    width: 100%;
    height: 100%;
  }
  .toast-timer circle {
    fill: transparent;
    stroke-width: 2.5;
    stroke: var(--primary);
    stroke-dasharray: 50.26; /* 2 * PI * 8 */
    stroke-dashoffset: 0;
    animation: countdown linear forwards;
  }
  @keyframes countdown {
    from { stroke-dashoffset: 0; }
    to { stroke-dashoffset: 50.26; }
  }
</style>