import { writable } from 'svelte/store';

function createConfirmStore() {
    const { subscribe, set, update } = writable({
        show: false,
        title: '',
        message: '',
        okText: 'OK',
        cancelText: 'Cancel',
        isDanger: false,
        resolve: null
    });

    return {
        subscribe,
        ask: (title, message, okText = 'OK', cancelText = 'Cancel', isDanger = false) => {
            return new Promise((resolve) => {
                set({
                    show: true,
                    title,
                    message,
                    okText,
                    cancelText,
                    isDanger,
                    resolve
                });
            });
        },
        close: (result) => {
            update(state => {
                if (state.resolve) state.resolve(result);
                return { ...state, show: false, resolve: null };
            });
        }
    };
}

export const confirmModal = createConfirmStore();