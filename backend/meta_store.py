import os
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


MetaDict = Dict[str, Dict[str, int]]


DEFAULT_META: Dict[str, int] = {
    "prospectos_totales": 0,
    "prospectos_digitales": 0,
    "contactados": 0,
    "visitas_sala": 0,
    "separaciones_totales": 0,
    "metas_minutas": 0,
}


# ==================== SYNC STATUS STORE ====================

class SyncStatusStore:
    """Almacena estado de sincronización para coordinar entre usuarios."""
    
    def get_status(self) -> Dict[str, Any]:
        raise NotImplementedError
    
    def set_syncing(self, is_syncing: bool, message: str = "") -> None:
        raise NotImplementedError
    
    def set_completed(self, message: str = "Sincronización completada") -> None:
        raise NotImplementedError
    
    def set_error(self, message: str) -> None:
        raise NotImplementedError


@dataclass
class MemorySyncStatusStore(SyncStatusStore):
    """Fallback en memoria (no compartido entre instancias)."""
    _status: Dict[str, Any] = field(default_factory=lambda: {
        "state": "Ready",
        "message": "Sistema listo",
        "last_updated": None,
        "sync_started_at": None
    })
    
    def get_status(self) -> Dict[str, Any]:
        return self._status.copy()
    
    def set_syncing(self, is_syncing: bool, message: str = "") -> None:
        self._status["state"] = "Syncing" if is_syncing else "Ready"
        self._status["message"] = message or ("Sincronizando..." if is_syncing else "Sistema listo")
        if is_syncing:
            self._status["sync_started_at"] = datetime.now().isoformat()
    
    def set_completed(self, message: str = "Sincronización completada") -> None:
        self._status["state"] = "Ready"
        self._status["message"] = message
        self._status["last_updated"] = datetime.now().isoformat()
        self._status["sync_started_at"] = None
    
    def set_error(self, message: str) -> None:
        self._status["state"] = "Error"
        self._status["message"] = message
        self._status["sync_started_at"] = None


@dataclass
class SupabaseSyncStatusStore(SyncStatusStore):
    """Estado de sync compartido via Supabase."""
    url: str
    key: str
    table: str = "sync_status"
    
    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
    
    def get_status(self) -> Dict[str, Any]:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{self.table}"
        params = {"select": "*", "id": "eq.1"}
        try:
            r = requests.get(endpoint, headers=self._headers(), params=params, timeout=10)
            if r.status_code >= 400:
                logger.error(f"Supabase get_status failed: {r.status_code}")
                return {"state": "Ready", "message": "Sistema listo", "last_updated": None}
            rows = r.json() or []
            if not rows:
                return {"state": "Ready", "message": "Sistema listo", "last_updated": None}
            row = rows[0]
            return {
                "state": row.get("state", "Ready"),
                "message": row.get("message", ""),
                "last_updated": row.get("last_updated"),
                "sync_started_at": row.get("sync_started_at")
            }
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {"state": "Ready", "message": "Sistema listo", "last_updated": None}
    
    def _upsert(self, data: Dict[str, Any]) -> None:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{self.table}"
        payload = {"id": 1, **data}
        headers = self._headers()
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        try:
            r = requests.post(
                endpoint,
                headers=headers,
                params={"on_conflict": "id"},
                json=[payload],
                timeout=10
            )
            if r.status_code >= 400:
                logger.error(f"Supabase sync status upsert failed: {r.status_code} {r.text}")
        except Exception as e:
            logger.error(f"Error upserting sync status: {e}")
    
    def set_syncing(self, is_syncing: bool, message: str = "") -> None:
        self._upsert({
            "state": "Syncing" if is_syncing else "Ready",
            "message": message or ("Descargando reportes de Evolta..." if is_syncing else "Sistema listo"),
            "sync_started_at": datetime.now().isoformat() if is_syncing else None
        })
    
    def set_completed(self, message: str = "Sincronización completada") -> None:
        self._upsert({
            "state": "Ready",
            "message": message,
            "last_updated": datetime.now().isoformat(),
            "sync_started_at": None
        })
    
    def set_error(self, message: str) -> None:
        self._upsert({
            "state": "Error",
            "message": message,
            "sync_started_at": None
        })


class MetaStore:
    def get_all(self) -> MetaDict:
        raise NotImplementedError

    def upsert_project(self, project: str, metas: Dict[str, int]) -> None:
        raise NotImplementedError


@dataclass
class FileMetaStore(MetaStore):
    path: str

    def get_all(self) -> MetaDict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
        except Exception as e:
            logger.error(f"Error reading meta file {self.path}: {e}")
            return {}

    def upsert_project(self, project: str, metas: Dict[str, int]) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        all_metas = self.get_all()
        current = all_metas.get(project, {}).copy()
        current.update(metas)
        all_metas[project] = current
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(all_metas, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error writing meta file {self.path}: {e}")


@dataclass
class SupabaseMetaStore(MetaStore):
    url: str
    key: str
    table: str = "metas"

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def get_all(self) -> MetaDict:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{self.table}"
        params = {"select": "*"}
        r = requests.get(endpoint, headers=self._headers(), params=params, timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase get_all failed: {r.status_code} {r.text}")
        rows = r.json() or []
        result: MetaDict = {}
        for row in rows:
            project = row.get("project")
            if not project:
                continue
            result[project] = {
                k: int(row.get(k) or 0)
                for k in DEFAULT_META.keys()
            }
        return result

    def upsert_project(self, project: str, metas: Dict[str, int]) -> None:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{self.table}"
        payload: Dict[str, Any] = {"project": project}
        for k, v in metas.items():
            if k in DEFAULT_META:
                payload[k] = int(v or 0)
        headers = self._headers()
        # Upsert by project
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        r = requests.post(
            endpoint,
            headers=headers,
            params={"on_conflict": "project"},
            json=[payload],
            timeout=30,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase upsert failed: {r.status_code} {r.text}")


def build_meta_store(download_dir: str) -> MetaStore:
    """Prefer Supabase if configured; fallback to local JSON file."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if supabase_url and supabase_key:
        logger.info("Meta store: Supabase")
        return SupabaseMetaStore(url=supabase_url, key=supabase_key)

    meta_path = os.path.join(download_dir, "meta_data.json")
    logger.info(f"Meta store: file ({meta_path})")
    return FileMetaStore(path=meta_path)


def build_sync_status_store() -> SyncStatusStore:
    """Prefer Supabase if configured; fallback to memory."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if supabase_url and supabase_key:
        logger.info("Sync status store: Supabase")
        return SupabaseSyncStatusStore(url=supabase_url, key=supabase_key)

    logger.info("Sync status store: Memory (not shared)")
    return MemorySyncStatusStore()
