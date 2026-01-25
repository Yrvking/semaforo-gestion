import os
import json
import logging
from dataclasses import dataclass
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
