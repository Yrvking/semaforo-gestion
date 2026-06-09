# 🚦 Semáforo de Gestión - Grupo Padova

Sistema de dashboard para monitoreo de métricas comerciales con sincronización automática desde Evolta.

## 📁 Estructura del Proyecto

```
SEMAFORO/
├── backend/           # API FastAPI + Selenium
│   ├── main.py        # Endpoints API
│   ├── scraper.py     # Web scraping Evolta
│   ├── processor.py   # Procesamiento de datos
│   ├── Dockerfile     # Para despliegue
│   └── requirements.txt
│
├── frontend/          # React + Vite
│   ├── src/
│   │   ├── components/
│   │   │   └── SemaforoExcel.jsx
│   │   └── services/
│   │       └── api.js
│   └── vercel.json    # Config Vercel
│
└── CREDENCIALES.txt   # Credenciales Evolta (local)
```

## 🚀 Despliegue Rápido

### Paso 1: Subir a GitHub

```bash
cd c:\Users\Yrving\SEMAFORO
git init
git add .
git commit -m "Initial commit - Semaforo de Gestion"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/semaforo-gestion.git
git push -u origin main
```

### Paso 2: Desplegar Backend en Railway

1. Ir a [railway.app](https://railway.app)
2. "New Project" → "Deploy from GitHub repo"
3. Seleccionar `backend/` como root directory
4. Agregar variables de entorno:
   ```
   EVOLTA_USERNAME=tu_usuario
   EVOLTA_PASSWORD=tu_password
   ENVIRONMENT=production
   DOWNLOAD_DIR=/app/downloads
   ALLOWED_ORIGINS=https://semaforo-gestion.vercel.app
   ```
5. Railway generará una URL como: `https://semaforo-backend-xxxxx.railway.app`

### Paso 3: Desplegar Frontend en Vercel

1. Ir a [vercel.com](https://vercel.com)
2. "Add New Project" → Importar repositorio
3. Seleccionar `frontend/` como root directory
4. Agregar variable de entorno:
   ```
   VITE_API_URL=https://semaforo-backend-xxxxx.railway.app
   ```
5. Click "Deploy"

`VITE_API_URL` debe ser únicamente el origen del backend. El frontend agrega
`/api` internamente y también tolera temporalmente configuraciones antiguas que
ya lo incluyan.

### Persistencia Railway

Configurar un volumen persistente montado en `/app/downloads`. Allí se guardan
el conjunto activo, `manifest.json`, metas locales y respaldos. Sin volumen, un
reinicio o nuevo despliegue puede eliminar esos archivos.

## 💻 Desarrollo Local

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## 🔒 Seguridad

- Las credenciales de Evolta se manejan via variables de entorno en producción
- El archivo `CREDENCIALES.txt` es solo para desarrollo local
- CORS está configurado para permitir solo orígenes específicos

## 📊 Funcionalidades

- ✅ Sincronización automática con Evolta
- ✅ Dashboard con semáforo de colores
- ✅ Configuración de metas mensuales
- ✅ Indicadores de rendimiento
- ✅ Vista global de todos los proyectos
- ✅ Diseño responsive y luxury

## 🛠️ Tecnologías

| Componente | Tecnología |
|------------|------------|
| Frontend | React 18 + Vite |
| Backend | FastAPI (Python) |
| Scraping | Selenium + Chrome |
| Hosting Frontend | Vercel |
| Hosting Backend | Railway |

---

Desarrollado por **WYLC** para Grupo Padova
