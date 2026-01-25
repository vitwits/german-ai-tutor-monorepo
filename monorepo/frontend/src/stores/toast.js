import { writable } from 'svelte/store';

export const toasts = writable([]);

export const addToast = (msg, type = 'info', duration = 4000) => {
  const id = Math.random();
  toasts.update((all) => [...all, { id, msg, type }]);
  setTimeout(() => removeToast(id), duration);
};

export const removeToast = (id) => {
  toasts.update((all) => all.filter((t) => t.id !== id));
};