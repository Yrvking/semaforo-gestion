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

- **Metas**: Puedes editar las metas mensuales directamente en la tabla

- **Semáforo**: Muestra el porcentaje de avance con colores:
  - 🟢 Verde: ≥90%
  - 🟡 Amarillo: 80-89%
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

Para agregar más proyectos, editar `TARGET_PROJECTS` en:
- `backend/processor.py`
- `frontend/src/components/SemaforoExcel.jsx`
