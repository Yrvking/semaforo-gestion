
import axios from 'axios';

// URL dinámica usando ngrok para conectar Vercel con servidor local
const BASE_URL = import.meta.env.VITE_API_URL || 'https://coleopterous-bertram-venomously.ngrok-free.dev';
const API_URL = `${BASE_URL}/api`;

const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true' // Evita la pantalla de advertencia de ngrok
    },
});

export const getStatus = () => api.get('/status');
export const getSemaforo = () => api.get('/semaforo');
export const syncData = (data) => api.post('/sync', data);
export const updateMeta = (project, metric, value) => api.post('/meta', { project, metric, value });

export default api;
