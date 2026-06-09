import React, { useEffect, useMemo, useState } from 'react';
import {
    getActiveCreditProcess,
    getAccumulatedCredit,
    getCreditProcess,
    getCreditResult,
    startCreditAnalysis,
} from '../services/api';
import './CreditoPanel.css';

const CREDIT_JOB_KEY = 'semaforo_credit_job_id';

const toIsoToday = () => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
};

const toIsoMonthStart = () => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    return `${y}-${m}-01`;
};

const toApiDate = (iso) => {
    const [y, m, d] = (iso || '').split('-');
    if (!y || !m || !d) return '';
    return `${d}/${m}/${y}`;
};

const resultadoEfectivo = (row) => {
    if (!row.tiene_score) return 'SIN DATOS';
    if (row.resultado === 'CUMPLE') return 'CUMPLE';
    if (row.resultado === 'NO CUMPLE') return 'NO CUMPLE';
    return 'REVISAR';
};

const badgeClass = (resultado) => {
    if (resultado === 'CUMPLE') return 'credito-badge green';
    if (resultado === 'NO CUMPLE') return 'credito-badge red';
    if (resultado === 'REVISAR') return 'credito-badge yellow';
    return 'credito-badge gray';
};

export default function CreditoPanel() {
    const [startDate, setStartDate] = useState(toIsoMonthStart());
    const [endDate, setEndDate] = useState(toIsoToday());
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [payload, setPayload] = useState(null);
    const [process, setProcess] = useState(null);
    const [projectFilter, setProjectFilter] = useState('');
    const [search, setSearch] = useState('');

    const rows = useMemo(() => payload?.prospectos || [], [payload]);

    const projects = useMemo(() => {
        return [...new Set(rows.map((r) => r.proyecto).filter(Boolean))].sort();
    }, [rows]);

    const filteredRows = useMemo(() => {
        const term = search.trim().toLowerCase();
        return rows.filter((r) => {
            if (projectFilter && r.proyecto !== projectFilter) return false;
            if (!term) return true;
            const haystack = `${r.nombre || ''} ${r.nombre_completo || ''} ${r.dni || ''}`.toLowerCase();
            return haystack.includes(term);
        });
    }, [rows, projectFilter, search]);

    const loadResult = async (jobId) => {
        const result = await getCreditResult(jobId);
        setPayload(result.data);
    };

    useEffect(() => {
        let cancelled = false;

        const restoreProcess = async () => {
            try {
                const savedId = localStorage.getItem(CREDIT_JOB_KEY);
                const response = savedId
                    ? await getCreditProcess(savedId)
                    : await getActiveCreditProcess();
                const restored = savedId ? response.data : response.data.process;
                if (!cancelled && restored) {
                    setProcess(restored);
                    localStorage.setItem(CREDIT_JOB_KEY, restored.id);
                    if (restored.status === 'completed') await loadResult(restored.id);
                }
            } catch (e) {
                if (e?.response?.status === 404) localStorage.removeItem(CREDIT_JOB_KEY);
            }
        };

        restoreProcess();
        return () => { cancelled = true; };
    }, []);

    useEffect(() => {
        if (!process?.id || !['queued', 'running'].includes(process.status)) return undefined;

        const timer = window.setInterval(async () => {
            try {
                const response = await getCreditProcess(process.id);
                const next = response.data;
                setProcess(next);
                if (next.status === 'completed') {
                    await loadResult(next.id);
                } else if (next.status === 'failed') {
                    setError(next.error || 'El análisis crediticio no pudo completarse.');
                }
            } catch (e) {
                setError(e?.response?.data?.detail || 'No se pudo consultar el progreso.');
            }
        }, 2000);

        return () => window.clearInterval(timer);
    }, [process?.id, process?.status]);

    const handleAnalyze = async () => {
        setError('');
        if (!startDate || !endDate) {
            setError('Selecciona fecha de inicio y fecha fin.');
            return;
        }
        if (startDate > endDate) {
            setError('La fecha de inicio no puede ser mayor a la fecha fin.');
            return;
        }

        setLoading(true);
        try {
            const res = await startCreditAnalysis({
                start_date: toApiDate(startDate),
                end_date: toApiDate(endDate),
            });
            setPayload(null);
            setProcess(res.data);
            localStorage.setItem(CREDIT_JOB_KEY, res.data.id);
        } catch (e) {
            setError(e?.response?.data?.detail || e.message || 'Error analizando perfil crediticio.');
        } finally {
            setLoading(false);
        }
    };

    const handleLoadSaved = async () => {
        setError('');
        if (!startDate || !endDate || startDate > endDate) {
            setError('Selecciona un rango de fechas válido.');
            return;
        }
        setLoading(true);
        try {
            const response = await getAccumulatedCredit(toApiDate(startDate), toApiDate(endDate));
            setPayload(response.data);
        } catch (e) {
            setError(e?.response?.data?.detail || 'No se pudieron consultar los datos guardados.');
        } finally {
            setLoading(false);
        }
    };

    const isRunning = ['queued', 'running'].includes(process?.status);
    const progress = Number(process?.progress || 0);

    return (
        <main className="main">
            <div className="credito-section">
                <h2>🧭 Perfil Crediticio de Prospectos</h2>

                <div className="credito-notice">
                    El análisis es independiente de la actualización del Semáforo y puede demorar varios minutos.
                    Puedes cambiar de pestaña y volver después; el proceso continuará en segundo plano.
                </div>

                <div className="credito-controls">
                    <div className="control-item">
                        <label>Desde:</label>
                        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} disabled={isRunning} />
                    </div>
                    <div className="control-item">
                        <label>Hasta:</label>
                        <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} disabled={isRunning} />
                    </div>
                    <button className="btn-sync-floating" onClick={handleAnalyze} disabled={loading || isRunning}>
                        {isRunning ? 'Análisis en proceso' : loading ? 'Iniciando...' : 'Analizar perfil crediticio'}
                    </button>
                    <button className="credito-secondary-button" onClick={handleLoadSaved} disabled={loading || isRunning}>
                        Consultar datos guardados
                    </button>
                </div>

                {error && <div className="credito-error">⚠️ {error}</div>}

                {process && (
                    <div className={`credito-progress-panel ${process.status}`}>
                        <div className="credito-progress-header">
                            <div>
                                <strong>{process.message || 'Preparando análisis'}</strong>
                                <span>{process.processed || 0} de {process.total || 0}</span>
                            </div>
                            <strong>{progress}%</strong>
                        </div>
                        <div
                            className="credito-progress-track"
                            role="progressbar"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            aria-valuenow={progress}
                        >
                            <div className="credito-progress-fill" style={{ width: `${progress}%` }} />
                        </div>
                        <div className="credito-progress-stage">
                            {process.source === 'automatico' ? 'Carga diaria automática' : 'Análisis manual'}
                            {' · '}{process.stage || 'queued'}
                        </div>
                    </div>
                )}

                {payload && (
                    <>
                        <div className="credito-kpis">
                            <div className="credito-kpi-card">
                                <span>Total</span>
                                <strong>{payload.total || 0}</strong>
                            </div>
                            <div className="credito-kpi-card">
                                <span>Con score</span>
                                <strong>{payload.con_score || 0}</strong>
                            </div>
                            <div className="credito-kpi-card">
                                <span>Sin datos</span>
                                <strong>{payload.sin_score || 0}</strong>
                            </div>
                        </div>

                        <div className="credito-project-row">
                            {(payload.resumen_por_proyecto || []).map((item) => (
                                <button
                                    key={item.proyecto}
                                    className={`credito-project-chip ${projectFilter === item.proyecto ? 'active' : ''}`}
                                    onClick={() => setProjectFilter(projectFilter === item.proyecto ? '' : item.proyecto)}
                                >
                                    {item.proyecto} ({item.total})
                                </button>
                            ))}
                        </div>

                        <div className="credito-controls secondary">
                            <div className="control-item">
                                <label>Proyecto:</label>
                                <select value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)}>
                                    <option value="">Todos</option>
                                    {projects.map((p) => (
                                        <option key={p} value={p}>{p}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="control-item">
                                <label>Buscar:</label>
                                <input
                                    type="text"
                                    value={search}
                                    onChange={(e) => setSearch(e.target.value)}
                                    placeholder="Nombre o DNI"
                                />
                            </div>
                        </div>

                        <div className="credito-table-wrap">
                            <table className="credito-table">
                                <thead>
                                    <tr>
                                        <th>#</th>
                                        <th>Proyecto</th>
                                        <th>Nombre</th>
                                        <th>DNI</th>
                                        <th>Score</th>
                                        <th>Resultado</th>
                                        <th>Capacidad Pago</th>
                                        <th>Deuda</th>
                                        <th>Responsable</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredRows.map((r, idx) => {
                                        const resultado = resultadoEfectivo(r);
                                        return (
                                            <tr key={`${r.dni}-${idx}`}>
                                                <td>{idx + 1}</td>
                                                <td>{r.proyecto || '-'}</td>
                                                <td>{r.nombre_completo || r.nombre || '-'}</td>
                                                <td>{r.dni || '-'}</td>
                                                <td>{r.score ?? 'Sin datos'}</td>
                                                <td><span className={badgeClass(resultado)}>{resultado}</span></td>
                                                <td>{r.capacidad_pago || '-'}</td>
                                                <td>{r.deuda_total ? `S/ ${Number(r.deuda_total).toFixed(2)}` : '-'}</td>
                                                <td>{r.responsable || '-'}</td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}
            </div>
        </main>
    );
}
