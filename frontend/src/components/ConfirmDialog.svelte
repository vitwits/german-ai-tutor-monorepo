<script>
    import { confirmModal } from "../stores/confirm";
    import { fade, scale } from "svelte/transition";
    import { cubicOut } from "svelte/easing";

    function handleClose(result) {
        confirmModal.close(result);
    }
</script>

{#if $confirmModal.show}
    <div class="modal-overlay" 
         onclick={(e) => { if (e.target === e.currentTarget) handleClose(false); }} 
         onkeydown={(e) => { if (e.key === 'Escape') handleClose(false); }}
         role="button" 
         tabindex="0" 
         transition:fade={{ duration: 100 }}>
        <div class="box-area" transition:scale={{ duration: 100, start: 0.9, easing: cubicOut }}>
            <h3 class="text-heading5" id="sys-confirm-title">{$confirmModal.title}</h3>
            <div class="sub-text" id="sys-confirm-body">{$confirmModal.message}</div>
            <div class="action-buttons">
                {#if $confirmModal.cancelText}
                    <button type="button" class="btn-text" onclick={() => handleClose(false)}>
                        <span>{$confirmModal.cancelText}</span>
                    </button>
                {/if}
                <button type="button" class="btn-contained {$confirmModal.isDanger ? 'btn-danger' : ''}" onclick={() => handleClose(true)}>
                    <span>{$confirmModal.okText}</span>
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    .modal-overlay {
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0, 0, 0, 0.6); z-index: 9999;
        display: flex; align-items: center; justify-content: center;
        backdrop-filter: blur(3px);
    }

    .box-area {
        background: var(--surface); padding: 30px; border-radius: var(--radius);
        box-shadow: 0 10px 25px rgba(0,0,0,0.2); width: 90%; max-width: 400px;
        display: flex; flex-direction: column; gap: 20px; border: 1px solid var(--border);
    }

    .text-heading5 { margin: 0; font-size: 1.25rem; font-weight: 500; color: var(--on-surface); }
    .sub-text { font-size: 0.95rem; color: var(--on-surface); opacity: 0.7; line-height: 1.5; }
    .action-buttons { display: flex; justify-content: flex-end; gap: 12px; margin-top: 10px; }
    
    .btn-danger { background-color: #d32f2f; color: white; }
    .btn-danger:hover { background-color: #b71c1c; }
</style>
