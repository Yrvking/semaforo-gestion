
import React, { useState, useEffect } from 'react';
import { getSemaforo, syncData, updateMeta, getStatus } from '../services/api';
import './SemaforoTable.css';

const TARGET_PROJECTS = ['SUNNY', 'LITORAL 900', 'HELIO - SANTA BEATRIZ', 'LOMAS DE CARABAYLLO'];
const METRICS = ['Leads Totales', 'Leads Digitales', 'Contactados', 'Visitas', 'Separaciones', 'Ventas'];

const SemaforoTable = () => {
    const [data, setData] = useState([]);
    const [status, setStatus] = useState({ state: 'Booting', message: '', last_updated: null });
    const [loading, setLoading] = useState(false);

    const fetchData = async () => {
        try {
            const response = await getSemaforo();
            setData(response.data.data);
            setStatus(response.data.status);
        } catch (error) {
            console.error("Error fetching data", error);
        }
    };

    const pollStatus = async () => {
        try {
            const res = await getStatus();
            setStatus(res.data);
            if (res.data.state === 'Syncing') {
                setTimeout(pollStatus, 2000);
            } else {
                fetchData();
            }
        } catch (error) {
            console.error(error);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // Auto refresh every 30s
        return () => clearInterval(interval);
    }, []);

    const handleSync = async () => {
        setLoading(true);
        try {
            await syncData();
            pollStatus();
        } catch (error) {
            alert("Sync failed to start: " + error.message);
        } finally {
            setLoading(false);
        }
    };

    const handleMetaChange = async (project, metric, newValue) => {
        const val = parseInt(newValue, 10) || 0;
        // Optimistic update
        const newData = data.map(d => {
            if (d.Proyecto === project) {
                return {
                    ...d,
                    Metrics: {
                        ...d.Metrics,
                        [metric]: { ...d.Metrics[metric], Meta: val }
                    }
                };
            }
            return d;
        });
        setData(newData);

        try {
            await updateMeta(project, metric, val);
        } catch (error) {
            console.error("Failed to save meta", error);
            fetchData(); // Revert on error
        }
    };

    const getRowData = (metric) => {
        return TARGET_PROJECTS.map(proj => {
            const projData = data.find(d => d.Proyecto === proj);
            if (!projData) return { real: 0, meta: 0 };
            const m = projData.Metrics[metric];
            return { real: m?.Real || 0, meta: m?.Meta || 0 };
        });
    };

    const calculateColorClass = (real, meta) => {
        if (meta === 0) return '';
        const pct = real / meta;
        if (pct >= 1) return 'val-green';
        if (pct >= 0.8) return 'val-yellow';
        return 'val-red';
    };

    const getStatusClass = (s) => {
        if (s === 'Error') return 'status-error';
        if (s === 'Ready') return 'status-ready';
        if (s === 'Syncing') return 'status-syncing';
        return '';
    }

    return (
        <div className="semaforo-container">
            <div className="header">
                <div className="title-section">
                    <h1>Semáforo de Gestión</h1>
                    <div className="subtitle">
                        <span>Carpeta de Descargas:</span>
                        <code className="folder-path">C:\Users\Yrving\Downloads\CARPETA_SEMAFORO</code>
                    </div>
                </div>

                <div className="controls">
                    <div className={`status-badge ${getStatusClass(status.state).replace('status-', '')}`}>
                        <span className="status-dot">●</span>
                        {status.state}
                    </div>
                    <button
                        onClick={handleSync}
                        disabled={status.state === 'Syncing' || loading}
                        className="sync-button"
                    >
                        {status.state === 'Syncing' ? (
                            <>
                                <svg className="animate-spin h-5 w-5 mr-3" viewBox="0 0 24 24" style={{ width: '20px' }}>
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                <span>SINCRONIZANDO...</span>
                            </>
                        ) : (
                            <>
                                <span>🔄 SINCRONIZAR DATA</span>
                            </>
                        )}
                    </button>
                    <p className="last-updated">
                        Actualizado: {status.last_updated ? new Date(status.last_updated).toLocaleString() : 'Nunca'}
                    </p>
                </div>
            </div>

            <div className="table-card">
                <table className="semaforo-table">
                    <thead>
                        <tr>
                            <th style={{ textAlign: 'left', width: '200px' }}>Métrica</th>
                            <th style={{ width: '80px' }}>Tipo</th>
                            {TARGET_PROJECTS.map(p => (
                                <th key={p} className="project-header">
                                    {p}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {METRICS.map((metric, idx) => {
                            const rowValues = getRowData(metric);
                            return (
                                <React.Fragment key={metric}>
                                    <tr>
                                        <td rowSpan="2" className="metric-cell">{metric}</td>
                                        <td className="type-cell">REAL</td>
                                        {rowValues.map((val, i) => (
                                            <td key={i} className={`value-cell ${calculateColorClass(val.real, val.meta)}`}>
                                                {val.real}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr>
                                        <td className="type-cell">META</td>
                                        {TARGET_PROJECTS.map((proj, i) => (
                                            <td key={i} className="value-cell" style={{ background: '#fff' }}>
                                                <input
                                                    type="number"
                                                    className="input-meta"
                                                    value={rowValues[i].meta}
                                                    placeholder="0"
                                                    onChange={(e) => handleMetaChange(proj, metric, e.target.value)}
                                                />
                                            </td>
                                        ))}
                                    </tr>
                                </React.Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {(status.message || status.state === 'Error') && (
                <div className="message-box">
                    <span>ℹ️ Info: {status.message}</span>
                </div>
            )}
        </div>
    );
};

export default SemaforoTable;
