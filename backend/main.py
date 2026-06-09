from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import zipfile
import io
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import os
import shutil
import uuid
from pathlib import Path

from scraper import EvoltaScraper, DOWNLOAD_DIR, get_default_period
from processor import SemaforoProcessor
from meta_store import build_sync_status_store
from report_pipeline import iter_downloadable_files, publish_report_set, validate_report_set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Semaforo API")

# CORS - Configuración para producción
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,https://semaforo-gestion.vercel.app",
    ).split(",")
    if origin.strip()
]
allowed_origin_regex = os.getenv(
    "ALLOWED_ORIGIN_REGEX",
    r"^https://semaforo-gestion-[a-z0-9-]+-padovas-projects\.vercel\.app$",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado global
processor = SemaforoProcessor(download_dir=DOWNLOAD_DIR)
sync_status_store = build_sync_status_store()


class MetaUpdate(BaseModel):
    project: str
    metric: str
    value: int


class BulkMetaUpdate(BaseModel):
    project: str
    metas: dict


@app.get("/")
def read_root():
    return {"message": "Semaforo API running"}


@app.get("/api/status")
def get_status():
    return sync_status_store.get_status()


@app.get("/api/debug/metas")
def debug_metas():
    """Endpoint de debug para verificar estado de metas"""
    import os
    meta_file = processor.meta_file
    store_type = type(processor.meta_store).__name__
    sync_store_type = type(sync_status_store).__name__
    return {
        "meta_store_type": store_type,
        "sync_store_type": sync_store_type,
        "meta_file_path": meta_file,
        "meta_file_exists": os.path.exists(meta_file),
        "download_dir": DOWNLOAD_DIR,
        "download_dir_exists": os.path.exists(DOWNLOAD_DIR),
        "metas_count": len(processor.meta),
        "metas_projects": list(processor.meta.keys()),
        "metas_data": processor.meta,
        "sync_status": sync_status_store.get_status()
    }


@app.get("/api/semaforo")
def get_semaforo():
    try:
        processor.load_data()
        metrics = processor.calculate_metrics()
        return {"data": metrics, "status": sync_status_store.get_status()}
    except Exception as e:
        logger.error(f"Error getting semaforo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metas")
def get_metas():
    """Obtiene todas las metas para edición"""
    try:
        return {"metas": processor.get_all_metas()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    pass

class SyncRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def run_sync_task(start_date: Optional[str] = None, end_date: Optional[str] = None):
    sync_status_store.set_syncing(True, "Descargando reportes de Evolta...")
    staging_dir = None

    try:
        if not (start_date and end_date):
            start_date, end_date = get_default_period()

        period_start = datetime.strptime(start_date, "%d/%m/%Y").date()
        period_end = datetime.strptime(end_date, "%d/%m/%Y").date()
        staging_dir = Path(DOWNLOAD_DIR) / ".staging" / uuid.uuid4().hex
        staging_dir.mkdir(parents=True, exist_ok=False)

        sync_scraper = EvoltaScraper(download_dir=str(staging_dir))
        sync_scraper.run_sync(start_date, end_date)

        sync_status_store.set_syncing(True, "Validando los cuatro reportes...")
        validation = validate_report_set(staging_dir, period_start, period_end)

        sync_status_store.set_syncing(True, "Respaldando y publicando datos...")
        get_all_metas = getattr(processor, "get_all_metas", None)
        goals = get_all_metas() if callable(get_all_metas) else getattr(processor, "meta", {})
        publish_report_set(staging_dir, DOWNLOAD_DIR, validation, goals=goals)

        processor.load_data()
        sync_status_store.set_completed(
            f"Sincronización completada: {start_date} - {end_date}"
        )
        logger.info("Sync completed successfully")
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sync_status_store.set_error(f"Error: {str(e)}")
    finally:
        if staging_dir:
            shutil.rmtree(staging_dir, ignore_errors=True)


@app.post("/api/sync")
def trigger_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    current_status = sync_status_store.get_status()
    if current_status.get("state") == "Syncing":
        raise HTTPException(
            status_code=400, 
            detail="Ya hay una sincronización en progreso. Por favor espere."
        )
    
    logger.info(f"Triggering sync with dates: {request.start_date} - {request.end_date}")
    background_tasks.add_task(run_sync_task, request.start_date, request.end_date)
    return {"message": "Sincronización iniciada"}


@app.post("/api/meta")
def update_meta(update: MetaUpdate):
    try:
        processor.update_project_meta(update.project, update.metric, update.value)
        return {"message": "Meta actualizada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Resetear estado si se quedó pegado en 'Syncing' tras un reinicio"""
    try:
        status = sync_status_store.get_status()
        if status.get("state") == "Syncing":
            logger.warning("Found stuck Syncing state on startup. Resetting.")
            sync_status_store.set_error("Sincronización interrumpida por reinicio del servidor")
    except Exception as e:
        logger.error(f"Error checking startup status: {e}")


@app.post("/api/reset-status")
def reset_status():
    """Limpia un estado de error o sync interrumpido y vuelve a Ready"""
    try:
        sync_status_store.set_completed("Estado restablecido manualmente")
        return {"message": "Estado restablecido"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/metas/bulk")
def update_metas_bulk(update: BulkMetaUpdate):
    """Actualiza todas las metas de un proyecto"""
    try:
        processor.update_project_metas(update.project, update.metas)
        return {"message": "Metas actualizadas"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/download-reports')
def download_reports():
    try:
        if not os.path.exists(DOWNLOAD_DIR):
            raise HTTPException(status_code=404, detail='No hay reportes descargados')
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            files = list(iter_downloadable_files(DOWNLOAD_DIR))
            if not files:
                raise HTTPException(status_code=404, detail='No hay reportes publicados')
            for file_path in files:
                zip_file.write(file_path, file_path.name)
        zip_buffer.seek(0)
        return StreamingResponse(zip_buffer, media_type='application/zip', headers={'Content-Disposition': 'attachment; filename=reportes_evolta.zip'})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error zipping reports: {e}')
        raise HTTPException(status_code=500, detail=str(e))
