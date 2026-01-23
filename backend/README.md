# Semáforo de Gestión - Backend

API Backend para el sistema de Semáforo de Gestión de Grupo Padova.

## Tecnologías
- FastAPI (Python 3.11)
- Selenium + Chrome (Web Scraping)
- Pandas (Procesamiento de Excel)

## Desarrollo Local

```bash
# Crear entorno virtual
python -m venv .venv

# Activar entorno
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
uvicorn main:app --reload --port 8000
```

## Variables de Entorno

Crear archivo `.env` basado en `.env.example`:

```env
EVOLTA_USERNAME=tu_usuario
EVOLTA_PASSWORD=tu_password
ENVIRONMENT=development
DOWNLOAD_DIR=C:\Users\TuUsuario\Downloads\CARPETA_SEMAFORO
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Despliegue en Railway

1. Crear cuenta en [Railway](https://railway.app)
2. Conectar repositorio de GitHub
3. Configurar variables de entorno en Railway Dashboard:
   - `EVOLTA_USERNAME`
   - `EVOLTA_PASSWORD`
   - `ENVIRONMENT=production`
   - `DOWNLOAD_DIR=/app/downloads`
   - `ALLOWED_ORIGINS=https://tu-frontend.vercel.app`

4. Railway detectará el Dockerfile automáticamente

## Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/api/status` | Estado del sistema |
| GET | `/api/semaforo` | Datos del semáforo |
| GET | `/api/metas` | Obtener metas |
| POST | `/api/sync` | Sincronizar datos |
| POST | `/api/meta` | Actualizar meta individual |
| POST | `/api/metas/bulk` | Actualizar metas en bulk |
