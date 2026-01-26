import { writable } from 'svelte/store';

export const toasts = writable([]);

/**
 * @param {string} msg The message to display.
 * @param {'info' | 'success' | 'error'} type The type of toast.
 * @param {() => void} [onUndo] A callback function to execute when the "Undo" button is clicked.
 * @param {number} duration The duration in milliseconds for the toast to be visible.
 */
export const addToast = (msg, type = 'info', onUndo = null, duration = 5000) => {
  const id = Math.random();
  // Set up a timeout to automatically remove the toast.
  // The ID of this timeout is stored so it can be cleared if the user clicks "Undo".
  const timeoutId = setTimeout(() => removeToast(id), duration);

  const toast = { id, msg, type, onUndo, duration, timeoutId };
  toasts.update((all) => [toast, ...all]);
};

export const removeToast = (id) => {
  toasts.update((all) => {
    const toastToRemove = all.find(t => t.id === id);
    if (toastToRemove && toastToRemove.timeoutId) {
        clearTimeout(toastToRemove.timeoutId);
    }
    return all.filter((t) => t.id !== id);
  });
};