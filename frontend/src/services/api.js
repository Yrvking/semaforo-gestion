
import axios from 'axios';

// URL dinámica: usa variable de entorno en producción, localhost en desarrollo
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_URL = `${BASE_URL}/api`;

const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const getStatus = () => api.get('/status');
export const getSemaforo = () => api.get('/semaforo');
export const syncData = (data) => api.post('/sync', data);
export const updateMeta = (project, metric, value) => api.post('/meta', { project, metric, value });

export default api;
