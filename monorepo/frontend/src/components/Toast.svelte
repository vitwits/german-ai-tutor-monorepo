<script>
  import { toasts, removeToast } from "../stores/toast";
  import { flip } from "svelte/animate";
  import { fade, fly } from "svelte/transition";
</script>

<div class="toast-container">
  {#each $toasts as toast (toast.id)}
    <div class="toast {toast.type}" animate:flip transition:fly={{ y: 20, duration: 300 }}>
      <span>{toast.msg}</span>
      <button class="close-btn" onclick={() => removeToast(toast.id)}>×</button>
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
    display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 280px;
    border-left: 4px solid var(--primary); font-size: 0.9rem; font-weight: 500;
  }
  .toast.error { border-left-color: #d32f2f; }
  .toast.success { border-left-color: #4CAF50; }
  .close-btn { background: none; border: none; font-size: 1.2rem; cursor: pointer; padding: 0; color: inherit; opacity: 0.6; }
</style>