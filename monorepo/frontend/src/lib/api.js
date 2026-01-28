import axios from 'axios';
import { get } from 'svelte/store';
import { token, refreshToken, user } from '../stores/auth';
import { router } from 'tinro';

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

// Interceptor для обробки помилок 401 (Unauthorized)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        // Спробуємо оновити токен
        const rToken = get(refreshToken);
        if (!rToken) {
          throw new Error("No refresh token");
        }
        
        const res = await axios.post('/api/auth/refresh', { refresh_token: rToken });
        const newAccessToken = res.data.access_token;
        
        // Зберігаємо новий токен
        token.set(newAccessToken);
        localStorage.setItem('token', newAccessToken);
        
        // Повторюємо оригінальний запит з новим токеном
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh не вдався - логіним користувача
        console.log("🔐 Refresh failed. Redirecting to login...");
        token.set(null);
        refreshToken.set(null);
        user.set(null);
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        router.goto('/login');
        
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

export default api;