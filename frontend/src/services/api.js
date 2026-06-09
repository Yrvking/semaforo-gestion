
import axios from 'axios';

// VITE_API_URL representa el origen del backend. Se tolera un /api antiguo
// para no romper despliegues existentes mientras se actualiza Vercel.
const CONFIGURED_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const BASE_URL = CONFIGURED_URL.replace(/\/+$/, '').replace(/\/api$/, '');
export const API_URL = `${BASE_URL}/api`;

const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const getStatus = () => api.get('/status');
export const getSemaforo = () => api.get('/semaforo');
export const getMetas = () => api.get('/metas');
export const syncData = (data = {}) => api.post('/sync', data);
export const startCreditAnalysis = (data = {}) => api.post('/credito/procesos', data);
export const getCreditProcess = (jobId) => api.get(`/credito/procesos/${jobId}`);
export const getActiveCreditProcess = () => api.get('/credito/procesos/actual');
export const getCreditResult = (jobId) => api.get(`/credito/procesos/${jobId}/resultado`);
export const getAccumulatedCredit = (startDate, endDate) => api.get('/credito/acumulado', {
    params: { start_date: startDate, end_date: endDate },
});
export const updateMeta = (project, metric, value) => api.post('/meta', { project, metric, value });
export const updateMetasBulk = (project, metas) => api.post('/metas/bulk', { project, metas });
export const resetSyncStatus = () => api.post('/reset-status');
export const reportsDownloadUrl = `${API_URL}/download-reports`;

export default api;
