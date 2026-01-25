from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import logging
import os

from scraper import EvoltaScraper, DOWNLOAD_DIR
from processor import SemaforoProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Semaforo API")

# CORS - Configuración para producción
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado global
processor = SemaforoProcessor(download_dir=DOWNLOAD_DIR)
scraper = EvoltaScraper(download_dir=DOWNLOAD_DIR)
status = {
    "state": "Ready", 
    "message": "Sistema listo", 
    "last_updated": None
}


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
    return status


@app.get("/api/debug/metas")
def debug_metas():
    """Endpoint de debug para verificar estado de metas"""
    import os
    meta_file = processor.meta_file
    store_type = type(processor.meta_store).__name__
    return {
        "meta_store_type": store_type,
        "meta_file_path": meta_file,
        "meta_file_exists": os.path.exists(meta_file),
        "download_dir": DOWNLOAD_DIR,
        "download_dir_exists": os.path.exists(DOWNLOAD_DIR),
        "metas_count": len(processor.meta),
        "metas_projects": list(processor.meta.keys()),
        "metas_data": processor.meta
    }


@app.get("/api/semaforo")
def get_semaforo():
    try:
        processor.load_data()
        metrics = processor.calculate_metrics()
        return {"data": metrics, "status": status}
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


def run_sync_task():
    global status
    status["state"] = "Syncing"
    status["message"] = "Descargando reportes de Evolta..."
    
    try:
        scraper.run_sync()
        status["message"] = "Procesando datos..."
        processor.load_data()
        status["state"] = "Ready"
        status["message"] = "Sincronización completada"
        status["last_updated"] = datetime.now().isoformat()
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        status["state"] = "Error"
        status["message"] = f"Error: {str(e)}"


@app.post("/api/sync")
def trigger_sync(background_tasks: BackgroundTasks):
    if status["state"] == "Syncing":
        raise HTTPException(status_code=400, detail="Sync ya está en progreso")
    
    background_tasks.add_task(run_sync_task)
    return {"message": "Sync iniciado"}


@app.post("/api/meta")
def update_meta(update: MetaUpdate):
    try:
        processor.update_project_meta(update.project, update.metric, update.value)
        return {"message": "Meta actualizada"}
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
