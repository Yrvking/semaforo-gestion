# SEMÁFORO DE GESTIÓN

Sistema web para descargar reportes de Evolta y mostrar métricas de gestión.

## Estructura del Proyecto

```
SEMAFORO/
├── backend/           # API FastAPI
│   ├── main.py       # Endpoints de la API
│   ├── scraper.py    # Descarga de Evolta con Selenium
│   └── processor.py  # Procesamiento de datos Excel
├── frontend/          # Interfaz React + Vite
├── CREDENCIALES.txt   # Usuario y contraseña de Evolta
├── meta_data.json     # Metas guardadas
└── iniciar.ps1        # Script para iniciar todo
```

## Requisitos

- Python 3.10+
- Node.js 18+
- Google Chrome instalado

## Instalación

1. **Backend (una vez):**
```powershell
cd backend
pip install -r requirements.txt
```

2. **Frontend (una vez):**
```powershell
cd frontend
npm install
```

## Uso

### Opción 1: Script automático
```powershell
.\iniciar.ps1
```

### Opción 2: Manual

**Terminal 1 - Backend:**
```powershell
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```powershell
cd frontend
npm run dev
```

3. Abrir navegador en: http://localhost:5173

## Funcionalidades

- **Sincronizar**: Descarga automáticamente los 4 reportes de Evolta:
  - Prospectos
  - Ventas
  - Separaciones
  - Visitas

  Los cuatro reportes deben descargarse y validarse correctamente. Si uno falla,
  el sistema conserva la última versión válida y muestra el motivo del error.

- **Metas**: Puedes editar las metas mensuales directamente en la tabla

- **Semáforo**: Muestra el porcentaje de avance con colores:
  - 🟢 Verde: ≥100%
  - 🟡 Amarillo: 80-99%
  - 🔴 Rojo: <80%

## Archivos descargados

Los reportes se guardan en:
```
C:\Users\Yrving\Downloads\CARPETA_SEMAFORO\
```

## Credenciales

Editar `CREDENCIALES.txt`:
```
Usuario: TuUsuario
Contraseña: TuContraseña
```

## Proyectos monitoreados

- SUNNY
- LITORAL 900
- HELIO - SANTA BEATRIZ
- LOMAS DE CARABAYLLO
- DOMINGO ORUE

La lista central del backend está en `backend/report_pipeline.py` y la lista de
presentación está en `frontend/src/components/SemaforoExcel.jsx`.

## Periodo y respaldos

- Sin fechas manuales, descarga desde el primer día del mes hasta ayer usando
  la zona horaria `America/Lima`.
- Los reportes se descargan primero en una carpeta temporal.
- Solo se publican cuando los cuatro archivos superan las validaciones.
- Antes de publicar se crea un respaldo en `backups/<fecha-hora>/`.
- `manifest.json` registra periodo, filas, tamaños, fechas y metas vigentes.
