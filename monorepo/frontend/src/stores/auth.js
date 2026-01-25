import { writable, get } from 'svelte/store';
import api from '../lib/api';
import { router } from 'tinro';

// Стан
export const user = writable(null);
export const token = writable(localStorage.getItem('token') || null);
export const isAuthenticated = writable(!!localStorage.getItem('token'));

// Дії
export const login = async (email, password) => {
    try {
        // FastAPI OAuth2PasswordRequestForm очікує form-data, де email це 'username'
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);

        const res = await api.post('/auth/login', formData);
        const accessToken = res.data.access_token;
        
        token.set(accessToken);
        isAuthenticated.set(true);
        localStorage.setItem('token', accessToken);
        
        await fetchUser();
        router.goto('/');
        return { ok: true };
    } catch (e) {
        console.error(e);
        return { ok: false, error: e.response?.data?.detail || 'Login failed' };
    }
};

export const register = async (email, password) => {
    try {
        await api.post('/auth/register', { email, password });
        return { ok: true };
    } catch (e) {
        console.error(e);
        return { ok: false, error: e.response?.data?.detail || 'Registration failed' };
    }
};

export const logout = () => {
    token.set(null);
    user.set(null);
    isAuthenticated.set(false);
    localStorage.removeItem('token');
    router.goto('/login');
};

export const fetchUser = async () => {
    if (!get(token)) return;
    try {
        const res = await api.get('/auth/me');
        user.set(res.data);
    } catch (e) {
        logout();
    }
};
