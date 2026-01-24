import React, { useState, useEffect, useRef } from 'react';
import { getSemaforo, syncData, getStatus } from '../services/api';
import html2pdf from 'html2pdf.js';
import './SemaforoExcel.css';

// URL dinámica para API
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const PROJECTS = ['HELIO - SANTA BEATRIZ', 'LITORAL 900', 'LOMAS DE CARABAYLLO', 'SUNNY'];

const METRICS = [
    { label: 'LEADS TOTALES', key: 'Leads Totales', metaKey: 'prospectos_totales' },
    { label: 'LEADS DNI', key: 'Leads DNI', metaKey: null },
    { label: 'LEADS DIGITALES', key: 'Leads Digitales', metaKey: 'prospectos_digitales' },
    { label: 'PROSPECTOS', key: 'Prospectos', metaKey: 'contactados' },
    { label: 'VISITAS', key: 'Visitas Totales', metaKey: 'visitas_sala' },
    { label: 'SEPARACIONES', key: 'Separaciones Totales', metaKey: 'separaciones_totales' },
    { label: 'VENTAS', key: 'Ventas Totales', metaKey: 'metas_minutas' }
];

const META_FIELDS = [
    { key: 'prospectos_totales', label: 'Leads Totales' },
    { key: 'prospectos_digitales', label: 'Leads Digitales' },
    { key: 'contactados', label: 'Prospectos' },
    { key: 'visitas_sala', label: 'Visitas' },
    { key: 'separaciones_totales', label: 'Separaciones' },
    { key: 'metas_minutas', label: 'Ventas' }
];

const SemaforoExcel = () => {
    const [tab, setTab] = useState('semaforo');
    const [data, setData] = useState([]);
    const [metas, setMetas] = useState(() => {
        // Cargar metas desde localStorage al iniciar
        const saved = localStorage.getItem('semaforo_metas');
        return saved ? JSON.parse(saved) : {};
    });
    const [status, setStatus] = useState({ state: 'Loading', message: '', last_updated: null });
    const [loading, setLoading] = useState(false);
    const [fecha, setFecha] = useState(() => new Date().toISOString().split('T')[0]);
    const [pctMeta, setPctMeta] = useState(0);

    // Guardar metas en localStorage cada vez que cambien
    useEffect(() => {
        if (Object.keys(metas).length > 0) {
            localStorage.setItem('semaforo_metas', JSON.stringify(metas));
            console.log('Metas guardadas en localStorage:', metas);
        }
    }, [metas]);

    useEffect(() => {
        const d = new Date(fecha);
        const dia = d.getDate();
        const ultimoDia = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
        setPctMeta(Math.round((dia / ultimoDia) * 100) / 100);
    }, [fecha]);

    const fetchData = async () => {
        try {
            const res = await getSemaforo();
            setData(res.data.data);
            setStatus(res.data.status);
        } catch (e) { console.error(e); }
    };

    const fetchMetas = async () => {
        try {
            const res = await fetch(`${API_URL}/metas`);
            const result = await res.json();
            const serverMetas = result.metas || {};
            
            // Combinar: usar localStorage si el servidor no tiene datos
            const localMetas = JSON.parse(localStorage.getItem('semaforo_metas') || '{}');
            
            // Para cada proyecto, usar servidor si tiene datos, sino usar localStorage
            const combinedMetas = {};
            for (const proj of PROJECTS) {
                const serverProj = serverMetas[proj] || {};
                const localProj = localMetas[proj] || {};
                
                // Verificar si el servidor tiene datos reales (no todos en 0)
                const serverHasData = Object.values(serverProj).some(v => v > 0);
                const localHasData = Object.values(localProj).some(v => v > 0);
                
                if (serverHasData) {
                    combinedMetas[proj] = serverProj;
                } else if (localHasData) {
                    combinedMetas[proj] = localProj;
                    // Sincronizar al servidor si tenemos datos locales
                    syncMetasToServer(proj, localProj);
                } else {
                    combinedMetas[proj] = serverProj;
                }
            }
            
            setMetas(combinedMetas);
            console.log('Metas cargadas (combinadas):', combinedMetas);
        } catch (e) { 
            console.error('Error fetching metas:', e);
            // Si falla el servidor, usar localStorage
            const localMetas = JSON.parse(localStorage.getItem('semaforo_metas') || '{}');
            if (Object.keys(localMetas).length > 0) {
                setMetas(localMetas);
                console.log('Usando metas de localStorage:', localMetas);
            }
        }
    };

    // Función para sincronizar metas al servidor
    const syncMetasToServer = async (proj, metasData) => {
        try {
            await fetch(`${API_URL}/metas/bulk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project: proj, metas: metasData })
            });
            console.log(`Metas sincronizadas al servidor para ${proj}`);
        } catch (e) {
            console.error('Error sincronizando metas:', e);
        }
    };

    const pollStatus = async () => {
        try {
            const res = await getStatus();
            setStatus(res.data);
            if (res.data.state === 'Syncing') setTimeout(pollStatus, 2000);
            else fetchData();
        } catch (e) { console.error(e); }
    };

    useEffect(() => {
        fetchData();
        fetchMetas();
        const iv = setInterval(fetchData, 60000);
        return () => clearInterval(iv);
    }, []);

    const handleSync = async () => {
        setLoading(true);
        try { await syncData(); pollStatus(); }
        catch (e) { alert("Error: " + e.message); }
        finally { setLoading(false); }
    };

    const handleMetaChange = (proj, field, val) => {
        setMetas(prev => ({ ...prev, [proj]: { ...prev[proj], [field]: parseInt(val) || 0 } }));
    };

    const saveMetas = async () => {
        try {
            for (const proj of PROJECTS) {
                if (metas[proj]) {
                    await fetch(`${API_URL}/metas/bulk`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ project: proj, metas: metas[proj] })
                    });
                }
            }
            alert('✅ Metas guardadas');
            fetchData();
        } catch (e) { alert("Error: " + e.message); }
    };

    const getReal = (proj, key) => {
        const p = data.find(x => x.Proyecto === proj);
        return p?.Metrics?.[key]?.Real || 0;
    };

    const getColor = (pct) => {
        if (pct >= 100) return 'green';
        if (pct >= 80) return 'yellow';
        return 'red';  // 0% a 79% es rojo
    };

    const formatFecha = (str) => {
        const d = new Date(str);
        return `${d.getDate().toString().padStart(2,'0')}/${(d.getMonth()+1).toString().padStart(2,'0')}/${d.getFullYear()}`;
    };

    const formatFechaCorta = (str) => {
        const d = new Date(str);
        return `${d.getDate().toString().padStart(2,'0')}/${(d.getMonth()+1).toString().padStart(2,'0')}`;
    };

    // KPI Cards data
    const getKpiData = (proj) => {
        const pm = metas[proj] || {};
        const leads = getReal(proj, 'Leads Totales');
        const leadsMeta = Math.ceil((pm.prospectos_totales || 0) * pctMeta);
        const prospectos = getReal(proj, 'Prospectos');
        const prospectosMeta = Math.ceil((pm.contactados || 0) * pctMeta);
        const visitas = getReal(proj, 'Visitas Totales');
        const visitasMeta = Math.ceil((pm.visitas_sala || 0) * pctMeta);
        const ventas = getReal(proj, 'Ventas Totales');
        const ventasMeta = Math.ceil((pm.metas_minutas || 0) * pctMeta);
        
        return {
            leads: { value: leads, meta: leadsMeta, pct: leadsMeta > 0 ? Math.round((leads/leadsMeta)*100) : 0 },
            prospectos: { value: prospectos, meta: prospectosMeta, pct: prospectosMeta > 0 ? Math.round((prospectos/prospectosMeta)*100) : 0 },
            visitas: { value: visitas, meta: visitasMeta, pct: visitasMeta > 0 ? Math.round((visitas/visitasMeta)*100) : 0 },
            ventas: { value: ventas, meta: ventasMeta, pct: ventasMeta > 0 ? Math.round((ventas/ventasMeta)*100) : 0 }
        };
    };

    const [showKpi, setShowKpi] = useState(false);
    const reportRef = useRef(null);

    // Función para exportar a PDF
    const exportToPDF = () => {
        const element = reportRef.current;
        const fecha_reporte = new Date().toLocaleDateString('es-PE', { 
            year: 'numeric', month: '2-digit', day: '2-digit' 
        }).replace(/\//g, '-');
        
        const opt = {
            margin: [10, 10, 10, 10],
            filename: `Semaforo_Gestion_${fecha_reporte}.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { 
                scale: 2, 
                useCORS: true,
                letterRendering: true,
                scrollY: 0
            },
            jsPDF: { 
                unit: 'mm', 
                format: 'a4', 
                orientation: 'landscape' 
            },
            pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
        };
        
        // Agregar clase para estilos de impresión
        element.classList.add('printing');
        
        html2pdf().set(opt).from(element).save().then(() => {
            element.classList.remove('printing');
        });
    };

    return (
        <div className="app">
            {/* HEADER MINIMALISTA - SIEMPRE ARRIBA */}
            <header className="header">
                <div className="header-left">
                    <div className="header-brand">
                        <span className="brand-grupo">GRUPO</span>
                        <span className="brand-name">PADOVA</span>
                    </div>
                    <h1>SEMÁFORO DE GESTIÓN</h1>
                </div>
                <div className="header-controls">
                    <button className={`btn-kpi ${showKpi ? 'active' : ''}`} onClick={() => setShowKpi(!showKpi)}>
                        {showKpi ? '▲ Ocultar Resumen' : '▼ Ver Resumen'}
                    </button>
                    <span className="header-separator"></span>
                    <button className={`btn-tab ${tab === 'semaforo' ? 'active' : ''}`} onClick={() => setTab('semaforo')}>
                        Semáforo
                    </button>
                    <button className={`btn-tab ${tab === 'meta' ? 'active' : ''}`} onClick={() => setTab('meta')}>
                        Metas
                    </button>
                    <button className={`btn-tab ${tab === 'indicadores' ? 'active' : ''}`} onClick={() => setTab('indicadores')}>
                        Indicadores
                    </button>
                    <button className={`btn-tab ${tab === 'globales' ? 'active' : ''}`} onClick={() => setTab('globales')}>
                        Globales
                    </button>
                    <button className={`btn-tab ${tab === 'info' ? 'active' : ''}`} onClick={() => setTab('info')}>
                        Ayuda
                    </button>
                </div>
                <button className="btn-sync-floating" onClick={handleSync} disabled={status.state === 'Syncing' || loading}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                    </svg>
                    {status.state === 'Syncing' ? 'Actualizando...' : 'Actualizar'}
                </button>
                <button className="btn-pdf" onClick={exportToPDF} title="Exportar a PDF">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
                        <path d="M12 3v6h6"/>
                        <path d="M9 13h6m-6 4h6"/>
                    </svg>
                    PDF
                </button>
            </header>

            {/* KPI CARDS - COLAPSABLE */}
            {showKpi && (
                <section className="kpi-section">
                    {PROJECTS.map(proj => {
                        const kpi = getKpiData(proj);
                        return (
                            <div className="kpi-card" key={proj}>
                                <div className="kpi-header">
                                    <h3>{proj}</h3>
                                    <span className="kpi-badge">ACTIVO</span>
                                </div>
                                <div className="kpi-grid-2x2">
                                    <div className="kpi-quadrant">
                                        <div className="kpi-icon-small">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                <path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                                            </svg>
                                        </div>
                                        <span className="kpi-quad-label">LEADS</span>
                                        <span className="kpi-quad-value">{kpi.leads.value.toLocaleString()}</span>
                                        <div className="kpi-quad-meta">
                                            <span>Meta: {kpi.leads.meta}</span>
                                            <span className={`kpi-quad-pct ${getColor(kpi.leads.pct)}`}>{kpi.leads.pct}%</span>
                                        </div>
                                    </div>
                                    <div className="kpi-quadrant">
                                        <div className="kpi-icon-small">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                <path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                                            </svg>
                                        </div>
                                        <span className="kpi-quad-label">PROSPECTOS</span>
                                        <span className="kpi-quad-value">{kpi.prospectos.value.toLocaleString()}</span>
                                        <div className="kpi-quad-meta">
                                            <span>Meta: {kpi.prospectos.meta}</span>
                                            <span className={`kpi-quad-pct ${getColor(kpi.prospectos.pct)}`}>{kpi.prospectos.pct}%</span>
                                        </div>
                                    </div>
                                    <div className="kpi-quadrant">
                                        <div className="kpi-icon-small">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
                                            </svg>
                                        </div>
                                        <span className="kpi-quad-label">VISITAS</span>
                                        <span className="kpi-quad-value">{kpi.visitas.value.toLocaleString()}</span>
                                        <div className="kpi-quad-meta">
                                            <span>Meta: {kpi.visitas.meta}</span>
                                            <span className={`kpi-quad-pct ${getColor(kpi.visitas.pct)}`}>{kpi.visitas.pct}%</span>
                                        </div>
                                    </div>
                                    <div className="kpi-quadrant">
                                        <div className="kpi-icon-small">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                <path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                            </svg>
                                        </div>
                                        <span className="kpi-quad-label">VENTAS</span>
                                        <span className="kpi-quad-value">{kpi.ventas.value.toLocaleString()}</span>
                                        <div className="kpi-quad-meta">
                                            <span>Meta: {kpi.ventas.meta}</span>
                                            <span className={`kpi-quad-pct ${getColor(kpi.ventas.pct)}`}>{kpi.ventas.pct}%</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </section>
            )}

            {/* CONTENIDO EXPORTABLE A PDF */}
            <div ref={reportRef} className="pdf-container">
                {/* Header para PDF */}
                <div className="pdf-header">
                    <div className="pdf-brand">
                        <span className="brand-grupo">GRUPO</span>
                        <span className="brand-name">PADOVA</span>
                    </div>
                    <div className="pdf-title">
                        <h2>SEMÁFORO DE GESTIÓN</h2>
                        <p>Fecha de Reporte: {new Date().toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' })} | Avance del mes: {Math.round(pctMeta * 100)}%</p>
                    </div>
                </div>

            {/* TAB SEMÁFORO */}
            {tab === 'semaforo' && (
                <main className="main">
                    {/* Barra de controles */}
                    <div className="controls-bar">
                        <div className="control-item">
                            <label>Fecha de corte:</label>
                            <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} />
                        </div>
                        <div className="control-item">
                            <label>Avance del mes:</label>
                            <span className="pct-badge">{Math.round(pctMeta * 100)}%</span>
                        </div>
                        <div className="legend">
                            <span className="leg red"></span> &lt;80%
                            <span className="leg yellow"></span> 80-99%
                            <span className="leg green"></span> ≥100%
                        </div>
                    </div>

                    {/* Tabla con 3 filas por proyecto */}
                    <div className="table-container">
                        <table className="semaforo-table">
                            <thead>
                                <tr>
                                    <th className="th-proyecto" colSpan="2">PROYECTOS</th>
                                    {METRICS.map(m => <th key={m.key}>{m.label}</th>)}
                                </tr>
                            </thead>
                            <tbody>
                                {PROJECTS.map(proj => {
                                    const pm = metas[proj] || {};
                                    return (
                                        <React.Fragment key={proj}>
                                            {/* Fila 1: META (100%) */}
                                            <tr className="row-meta100">
                                                <td rowSpan="3" className="td-project">{proj}</td>
                                                <td className="td-label">META (100%)</td>
                                                {METRICS.map(m => {
                                                    const metaTotal = m.metaKey ? (pm[m.metaKey] || 0) : '-';
                                                    return <td key={m.key} className="td-value">{metaTotal}</td>;
                                                })}
                                            </tr>
                                            {/* Fila 2: META AL DÍA */}
                                            <tr className="row-metadia">
                                                <td className="td-label">META AL {formatFechaCorta(fecha)}</td>
                                                {METRICS.map(m => {
                                                    const metaTotal = m.metaKey ? (pm[m.metaKey] || 0) : 0;
                                                    const metaDia = m.metaKey ? Math.ceil(metaTotal * pctMeta) : '-';
                                                    return <td key={m.key} className="td-value">{metaDia}</td>;
                                                })}
                                            </tr>
                                            {/* Fila 3: REAL */}
                                            <tr className="row-real">
                                                <td className="td-label">REAL</td>
                                                {METRICS.map(m => {
                                                    const real = getReal(proj, m.key);
                                                    const metaTotal = m.metaKey ? (pm[m.metaKey] || 0) : 0;
                                                    const metaDia = m.metaKey ? Math.ceil(metaTotal * pctMeta) : 0;
                                                    const pct = metaDia > 0 ? Math.round((real / metaDia) * 100) : (real > 0 ? 100 : 0);
                                                    const color = m.metaKey ? getColor(pct) : '';
                                                    return (
                                                        <td key={m.key} className={`td-real ${color}`}>
                                                            <span className="real-num">{real}</span>
                                                            {m.metaKey && <span className={`real-pct ${color}`}>{pct}%</span>}
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        </React.Fragment>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>

                    <footer className="status-bar">
                        {status.state} | {status.last_updated ? `Actualizado: ${new Date(status.last_updated).toLocaleString()}` : 'Sin sincronizar'}
                    </footer>
                </main>
            )}

            {/* TAB METAS */}
            {tab === 'meta' && (
                <main className="main">
                    <div className="meta-section">
                        <h2>🎯 Configuración de Metas Mensuales</h2>
                        <table className="meta-table">
                            <thead>
                                <tr>
                                    <th>MÉTRICA</th>
                                    {PROJECTS.map(p => <th key={p}>{p}</th>)}
                                </tr>
                            </thead>
                            <tbody>
                                {META_FIELDS.map(f => (
                                    <tr key={f.key}>
                                        <td className="td-label">{f.label}</td>
                                        {PROJECTS.map(proj => (
                                            <td key={proj}>
                                                <input
                                                    type="number"
                                                    value={metas[proj]?.[f.key] || 0}
                                                    onChange={e => handleMetaChange(proj, f.key, e.target.value)}
                                                />
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        <button className="btn-save" onClick={saveMetas}>💾 GUARDAR METAS</button>
                    </div>
                </main>
            )}

            {/* TAB INDICADORES */}
            {tab === 'indicadores' && (
                <main className="main">
                    <div className="indicadores-section">
                        <h2>📈 Indicadores de Rendimiento</h2>
                        
                        <div className="indicadores-grid">
                            {PROJECTS.map(proj => {
                                const leadsTotal = getReal(proj, 'Leads Totales');
                                const leadsDni = getReal(proj, 'Leads DNI');
                                const leadsDigitales = getReal(proj, 'Leads Digitales');
                                const prospectos = getReal(proj, 'Prospectos');
                                const visitas = getReal(proj, 'Visitas Totales');
                                const separaciones = getReal(proj, 'Separaciones Totales');
                                const ventas = getReal(proj, 'Ventas Totales');
                                
                                // Cálculo de ratios
                                const ratioProspectosLeads = leadsTotal > 0 ? ((prospectos / leadsTotal) * 100).toFixed(1) : 0;
                                const ratioVisita = prospectos > 0 ? ((visitas / prospectos) * 100).toFixed(1) : 0;
                                const ratioSeparacion = visitas > 0 ? ((separaciones / visitas) * 100).toFixed(1) : 0;
                                const ratioVenta = separaciones > 0 ? ((ventas / separaciones) * 100).toFixed(1) : 0;
                                const ratioDigital = leadsTotal > 0 ? ((leadsDigitales / leadsTotal) * 100).toFixed(1) : 0;
                                const ratioDni = leadsTotal > 0 ? ((leadsDni / leadsTotal) * 100).toFixed(1) : 0;
                                
                                return (
                                    <div className="indicador-card" key={proj}>
                                        <h3>{proj}</h3>
                                        <div className="indicador-list">
                                            <div className="indicador-item">
                                                <span className="indicador-label">Ratio Prospectos / Leads</span>
                                                <span className="indicador-formula">Prospectos / Leads</span>
                                                <span className="indicador-value">{ratioProspectosLeads}%</span>
                                            </div>
                                            <div className="indicador-item">
                                                <span className="indicador-label">Ratio Visita</span>
                                                <span className="indicador-formula">Visitas / Prospectos</span>
                                                <span className="indicador-value">{ratioVisita}%</span>
                                            </div>
                                            <div className="indicador-item">
                                                <span className="indicador-label">Ratio Separación</span>
                                                <span className="indicador-formula">Separaciones / Visitas</span>
                                                <span className="indicador-value">{ratioSeparacion}%</span>
                                            </div>
                                            <div className="indicador-item">
                                                <span className="indicador-label">Ratio Venta</span>
                                                <span className="indicador-formula">Ventas / Separaciones</span>
                                                <span className="indicador-value">{ratioVenta}%</span>
                                            </div>
                                            <div className="indicador-item">
                                                <span className="indicador-label">% Leads Digitales</span>
                                                <span className="indicador-formula">Digitales / Total</span>
                                                <span className="indicador-value">{ratioDigital}%</span>
                                            </div>
                                            <div className="indicador-item">
                                                <span className="indicador-label">% Leads con DNI</span>
                                                <span className="indicador-formula">Con DNI / Total</span>
                                                <span className="indicador-value">{ratioDni}%</span>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </main>
            )}

            {/* TAB GLOBALES */}
            {tab === 'globales' && (
                <main className="main">
                    <div className="globales-section">
                        <h2>🌐 Indicadores Globales - Todos los Proyectos</h2>
                        
                        {/* Resumen Global */}
                        {(() => {
                            // Calcular totales globales
                            let totalLeads = 0, totalLeadsDni = 0, totalLeadsDigitales = 0;
                            let totalProspectos = 0, totalVisitas = 0, totalSeparaciones = 0, totalVentas = 0;
                            let totalMetaLeads = 0, totalMetaProspectos = 0, totalMetaVisitas = 0, totalMetaVentas = 0;
                            
                            PROJECTS.forEach(proj => {
                                totalLeads += getReal(proj, 'Leads Totales');
                                totalLeadsDni += getReal(proj, 'Leads DNI');
                                totalLeadsDigitales += getReal(proj, 'Leads Digitales');
                                totalProspectos += getReal(proj, 'Prospectos');
                                totalVisitas += getReal(proj, 'Visitas Totales');
                                totalSeparaciones += getReal(proj, 'Separaciones Totales');
                                totalVentas += getReal(proj, 'Ventas Totales');
                                
                                const pm = metas[proj] || {};
                                totalMetaLeads += Math.ceil((pm.prospectos_totales || 0) * pctMeta);
                                totalMetaProspectos += Math.ceil((pm.contactados || 0) * pctMeta);
                                totalMetaVisitas += Math.ceil((pm.visitas_sala || 0) * pctMeta);
                                totalMetaVentas += Math.ceil((pm.metas_minutas || 0) * pctMeta);
                            });
                            
                            // Calcular porcentajes globales
                            const pctLeads = totalMetaLeads > 0 ? Math.round((totalLeads / totalMetaLeads) * 100) : 0;
                            const pctProspectos = totalMetaProspectos > 0 ? Math.round((totalProspectos / totalMetaProspectos) * 100) : 0;
                            const pctVisitas = totalMetaVisitas > 0 ? Math.round((totalVisitas / totalMetaVisitas) * 100) : 0;
                            const pctVentas = totalMetaVentas > 0 ? Math.round((totalVentas / totalMetaVentas) * 100) : 0;
                            
                            // Ratios globales
                            const ratioProspectosLeads = totalLeads > 0 ? ((totalProspectos / totalLeads) * 100).toFixed(1) : 0;
                            const ratioVisita = totalProspectos > 0 ? ((totalVisitas / totalProspectos) * 100).toFixed(1) : 0;
                            const ratioSeparacion = totalVisitas > 0 ? ((totalSeparaciones / totalVisitas) * 100).toFixed(1) : 0;
                            const ratioVenta = totalSeparaciones > 0 ? ((totalVentas / totalSeparaciones) * 100).toFixed(1) : 0;
                            const ratioDigital = totalLeads > 0 ? ((totalLeadsDigitales / totalLeads) * 100).toFixed(1) : 0;
                            const ratioDni = totalLeads > 0 ? ((totalLeadsDni / totalLeads) * 100).toFixed(1) : 0;
                            
                            return (
                                <>
                                    {/* KPIs Globales en Cards - Iconos Premium */}
                                    <div className="global-kpi-row">
                                        <div className="global-kpi-card">
                                            <div className="global-kpi-icon leads">
                                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                    <path d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>
                                                </svg>
                                            </div>
                                            <div className="global-kpi-info">
                                                <span className="global-kpi-label">LEADS TOTALES</span>
                                                <span className="global-kpi-value">{totalLeads.toLocaleString()}</span>
                                                <div className="global-kpi-meta">
                                                    <span>Meta: {totalMetaLeads}</span>
                                                    <span className={`global-kpi-pct ${getColor(pctLeads)}`}>{pctLeads}%</span>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="global-kpi-card">
                                            <div className="global-kpi-icon prospectos">
                                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                    <path d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"/>
                                                </svg>
                                            </div>
                                            <div className="global-kpi-info">
                                                <span className="global-kpi-label">PROSPECTOS</span>
                                                <span className="global-kpi-value">{totalProspectos.toLocaleString()}</span>
                                                <div className="global-kpi-meta">
                                                    <span>Meta: {totalMetaProspectos}</span>
                                                    <span className={`global-kpi-pct ${getColor(pctProspectos)}`}>{pctProspectos}%</span>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="global-kpi-card">
                                            <div className="global-kpi-icon visitas">
                                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                    <path d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3H21m-3.75 3H21"/>
                                                </svg>
                                            </div>
                                            <div className="global-kpi-info">
                                                <span className="global-kpi-label">VISITAS</span>
                                                <span className="global-kpi-value">{totalVisitas.toLocaleString()}</span>
                                                <div className="global-kpi-meta">
                                                    <span>Meta: {totalMetaVisitas}</span>
                                                    <span className={`global-kpi-pct ${getColor(pctVisitas)}`}>{pctVisitas}%</span>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="global-kpi-card">
                                            <div className="global-kpi-icon ventas">
                                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                                    <path d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z"/>
                                                </svg>
                                            </div>
                                            <div className="global-kpi-info">
                                                <span className="global-kpi-label">VENTAS</span>
                                                <span className="global-kpi-value">{totalVentas.toLocaleString()}</span>
                                                <div className="global-kpi-meta">
                                                    <span>Meta: {totalMetaVentas}</span>
                                                    <span className={`global-kpi-pct ${getColor(pctVentas)}`}>{pctVentas}%</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Ratios Globales */}
                                    <div className="global-ratios-container">
                                        <h3>📊 Ratios de Conversión Global</h3>
                                        <div className="global-ratios-grid">
                                            <div className="global-ratio-card">
                                                <span className="ratio-title">Ratio Prospectos / Leads</span>
                                                <span className="ratio-value">{ratioProspectosLeads}%</span>
                                                <span className="ratio-detail">{totalProspectos} / {totalLeads}</span>
                                            </div>
                                            <div className="global-ratio-card">
                                                <span className="ratio-title">Ratio Visita</span>
                                                <span className="ratio-value">{ratioVisita}%</span>
                                                <span className="ratio-detail">{totalVisitas} / {totalProspectos}</span>
                                            </div>
                                            <div className="global-ratio-card">
                                                <span className="ratio-title">Ratio Separación</span>
                                                <span className="ratio-value">{ratioSeparacion}%</span>
                                                <span className="ratio-detail">{totalSeparaciones} / {totalVisitas}</span>
                                            </div>
                                            <div className="global-ratio-card">
                                                <span className="ratio-title">Ratio Venta</span>
                                                <span className="ratio-value">{ratioVenta}%</span>
                                                <span className="ratio-detail">{totalVentas} / {totalSeparaciones}</span>
                                            </div>
                                            <div className="global-ratio-card">
                                                <span className="ratio-title">% Leads Digitales</span>
                                                <span className="ratio-value">{ratioDigital}%</span>
                                                <span className="ratio-detail">{totalLeadsDigitales} / {totalLeads}</span>
                                            </div>
                                            <div className="global-ratio-card">
                                                <span className="ratio-title">% Leads con DNI</span>
                                                <span className="ratio-value">{ratioDni}%</span>
                                                <span className="ratio-detail">{totalLeadsDni} / {totalLeads}</span>
                                            </div>
                                        </div>
                                    </div>
                                </>
                            );
                        })()}
                    </div>
                </main>
            )}

            {/* TAB AYUDA/INFO */}
            {tab === 'info' && (
                <main className="main">
                    <div className="info-section">
                        <h2>📖 Manual de Usuario - Semáforo de Gestión</h2>
                        
                        <div className="info-card">
                            <h3>🔄 ¿Cómo funciona el sistema?</h3>
                            <ol>
                                <li><strong>Actualizar:</strong> El botón "Actualizar" descarga automáticamente 4 reportes desde Evolta:
                                    <ul>
                                        <li>Reporte de Prospectos (Leads)</li>
                                        <li>Reporte de Ventas</li>
                                        <li>Reporte de Separaciones</li>
                                        <li>Reporte de Visitas</li>
                                    </ul>
                                </li>
                                <li><strong>Procesar:</strong> El sistema procesa los archivos Excel y calcula las métricas por proyecto.</li>
                                <li><strong>Mostrar:</strong> Los resultados se muestran en la tabla con el semáforo de colores.</li>
                            </ol>
                        </div>

                        <div className="info-card">
                            <h3>📑 Pestañas del Sistema</h3>
                            <ul>
                                <li><strong>Ver Resumen:</strong> Muestra/oculta los KPIs con cuadrantes por proyecto</li>
                                <li><strong>Semáforo:</strong> Tabla principal con métricas y colores por proyecto</li>
                                <li><strong>Metas:</strong> Configuración de metas mensuales por proyecto</li>
                                <li><strong>Indicadores:</strong> Ratios de conversión del funnel por proyecto</li>
                                <li><strong>Globales:</strong> Indicadores consolidados de todos los proyectos</li>
                                <li><strong>Ayuda:</strong> Este manual de usuario</li>
                            </ul>
                        </div>

                        <div className="info-card">
                            <h3>🌐 Pestaña GLOBALES</h3>
                            <p>Muestra indicadores consolidados de todos los proyectos:</p>
                            <ul>
                                <li><strong>KPIs Totales:</strong> Suma de Leads, Prospectos, Visitas y Ventas de todos los proyectos</li>
                                <li><strong>Ratios Globales:</strong> Ratios de conversión calculados sobre el total</li>
                                <li><strong>Tabla Comparativa:</strong> Comparación lado a lado de todos los proyectos</li>
                            </ul>
                        </div>

                        <div className="info-card">
                            <h3>📈 Pestaña INDICADORES</h3>
                            <p>Muestra los ratios de conversión del funnel de ventas:</p>
                            <table className="formula-table">
                                <thead>
                                    <tr>
                                        <th>Indicador</th>
                                        <th>Fórmula</th>
                                        <th>Descripción</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td><strong>Ratio Prospectos / Leads</strong></td>
                                        <td><code>(Prospectos / Leads) × 100</code></td>
                                        <td>% de leads que fueron contactados</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Ratio Visita</strong></td>
                                        <td><code>(Visitas / Prospectos) × 100</code></td>
                                        <td>% de prospectos que visitaron</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Ratio Separación</strong></td>
                                        <td><code>(Separaciones / Visitas) × 100</code></td>
                                        <td>% de visitas que separaron</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Ratio Venta</strong></td>
                                        <td><code>(Ventas / Separaciones) × 100</code></td>
                                        <td>% de separaciones que cerraron venta</td>
                                    </tr>
                                    <tr>
                                        <td><strong>% Leads Digitales</strong></td>
                                        <td><code>(Leads Digitales / Leads) × 100</code></td>
                                        <td>Proporción de leads de origen digital</td>
                                    </tr>
                                    <tr>
                                        <td><strong>% Leads con DNI</strong></td>
                                        <td><code>(Leads DNI / Leads) × 100</code></td>
                                        <td>Proporción de leads con documento registrado</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <div className="info-card">
                            <h3>📊 Métricas y Fórmulas (basadas en módulos VBA)</h3>
                            <table className="formula-table">
                                <thead>
                                    <tr>
                                        <th>Métrica</th>
                                        <th>Fórmula / Condiciones</th>
                                        <th>Archivo</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td><strong>LEADS TOTALES</strong></td>
                                        <td>
                                            <code>Proyecto = [PROYECTO]</code><br/>
                                            <code>LeadUnicoxMesProyecto = "SI"</code>
                                        </td>
                                        <td>reporteProspectos.xlsx</td>
                                    </tr>
                                    <tr>
                                        <td><strong>LEADS DNI</strong></td>
                                        <td>
                                            <code>Proyecto = [PROYECTO]</code><br/>
                                            <code>LeadUnicoxMesProyecto = "SI"</code><br/>
                                            <code>NroDocumento ≠ vacío</code>
                                        </td>
                                        <td>reporteProspectos.xlsx</td>
                                    </tr>
                                    <tr>
                                        <td><strong>LEADS DIGITALES</strong></td>
                                        <td>
                                            <code>Proyecto = [PROYECTO]</code><br/>
                                            <code>LeadUnicoxMesProyecto = "SI"</code><br/>
                                            <code>ComoSeEntero contiene:</code><br/>
                                            <em>META ADS, FACEBOOK, NEXO INMOBILIARIO, WHATSAPP, WHATSAPP FERIA, FERIA NEXO INMOBILIARIO, PAGINA WEB, TIK TOK ADS, INSTAGRAM, GOOGLE, DIGITAL</em>
                                        </td>
                                        <td>reporteProspectos.xlsx</td>
                                    </tr>
                                    <tr>
                                        <td><strong>PROSPECTOS</strong></td>
                                        <td>
                                            <code>Proyecto = [PROYECTO]</code><br/>
                                            <code>LeadUnicoxMesProyecto = "SI"</code><br/>
                                            <code>SubEstado = "CONTACTADO"</code>
                                        </td>
                                        <td>reporteProspectos.xlsx</td>
                                    </tr>
                                    <tr>
                                        <td><strong>VISITAS</strong></td>
                                        <td>
                                            <code>Proyecto = [PROYECTO]</code><br/>
                                            Cuenta de registros
                                        </td>
                                        <td>ReporteVisitas.xlsx</td>
                                    </tr>
                                    <tr>
                                        <td><strong>SEPARACIONES</strong></td>
                                        <td>
                                            <code>DescripcionProyecto = [PROYECTO]</code><br/>
                                            <code>TipoInmueble_1 = "Departamento"</code>
                                        </td>
                                        <td>Separacion.xlsx</td>
                                    </tr>
                                    <tr>
                                        <td><strong>VENTAS</strong></td>
                                        <td>
                                            <code>Proyecto = [PROYECTO]</code><br/>
                                            <code>TipoInmueble_1 = "Departamento"</code>
                                        </td>
                                        <td>ReporteVenta.xlsx</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <div className="info-card">
                            <h3>📅 Cálculo de Meta a la Fecha</h3>
                            <div className="formula-box">
                                <p><strong>Fórmula:</strong></p>
                                <code>META AL DÍA = META (100%) × (Día del mes / Días totales del mes)</code>
                                <p className="example">
                                    <strong>Ejemplo:</strong> Si hoy es 15 de enero (31 días) y la META es 100:<br/>
                                    META AL DÍA = 100 × (15/31) = 100 × 0.48 = <strong>48</strong>
                                </p>
                            </div>
                        </div>

                        <div className="info-card">
                            <h3>🚦 Semáforo de Colores</h3>
                            <div className="semaforo-legend">
                                <div className="sem-item">
                                    <span className="sem-color green"></span>
                                    <div>
                                        <strong>VERDE (≥100%)</strong>
                                        <p>Meta cumplida o superada. ¡Excelente!</p>
                                    </div>
                                </div>
                                <div className="sem-item">
                                    <span className="sem-color yellow"></span>
                                    <div>
                                        <strong>AMARILLO (80% - 99%)</strong>
                                        <p>Cerca de la meta. Requiere atención.</p>
                                    </div>
                                </div>
                                <div className="sem-item">
                                    <span className="sem-color red"></span>
                                    <div>
                                        <strong>ROJO (&lt;80%)</strong>
                                        <p>Por debajo de la meta. Acción urgente requerida.</p>
                                    </div>
                                </div>
                            </div>
                            <div className="formula-box">
                                <p><strong>Fórmula del Porcentaje:</strong></p>
                                <code>% = (REAL / META AL DÍA) × 100</code>
                            </div>
                        </div>

                        <div className="info-card">
                            <h3>🎯 Pestaña METAS</h3>
                            <p>En la pestaña METAS puedes configurar las metas mensuales para cada proyecto:</p>
                            <ul>
                                <li><strong>Leads Totales:</strong> Meta de prospectos totales del mes</li>
                                <li><strong>Leads Digitales:</strong> Meta de leads con origen digital</li>
                                <li><strong>Prospectos:</strong> Meta de leads contactados</li>
                                <li><strong>Visitas:</strong> Meta de visitas a sala de ventas</li>
                                <li><strong>Separaciones:</strong> Meta de separaciones del mes</li>
                                <li><strong>Ventas:</strong> Meta de ventas/minutas del mes</li>
                            </ul>
                            <p className="note">💡 Las metas se guardan automáticamente. Solo necesitas configurarlas una vez por mes.</p>
                        </div>

                        <div className="info-card">
                            <h3>📁 Proyectos Monitoreados</h3>
                            <ul className="project-list">
                                <li>🏢 HELIO - SANTA BEATRIZ</li>
                                <li>🏢 LITORAL 900</li>
                                <li>🏢 LOMAS DE CARABAYLLO</li>
                                <li>🏢 SUNNY</li>
                            </ul>
                        </div>

                        <div className="info-card">
                            <h3>⚠️ Notas Importantes</h3>
                            <ul>
                                <li>Los datos se actualizan al presionar "Actualizar"</li>
                                <li>La actualización puede tomar 1-2 minutos mientras descarga los reportes</li>
                                <li>Los archivos se descargan en: <code>C:\Users\Yrving\Downloads\CARPETA_SEMAFORO</code></li>
                                <li>El sistema usa credenciales guardadas para acceder a Evolta automáticamente</li>
                            </ul>
                        </div>
                    </div>
                </main>
            )}
            </div>{/* Fin pdf-container */}
            
            {/* Firma del desarrollador */}
            <div className="developer-signature">
                Desarrollado por <span>WYLC</span>
            </div>
        </div>
    );
};

export default SemaforoExcel;
