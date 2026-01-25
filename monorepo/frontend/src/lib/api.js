import axios from 'axios';
import { get } from 'svelte/store';
import { token } from '../stores/auth';

const api = axios.create({
  baseURL: '/api', // Vite proxy перенаправить це на http://localhost:8000/api
});

// Interceptor для додавання токена
api.interceptors.request.use((config) => {
  const t = get(token);
  if (t) {
    config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

export default api;