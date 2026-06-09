from __future__ import annotations

import os
import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests


LIMA_TZ = ZoneInfo("America/Lima")


def _now_iso() -> str:
    return datetime.now(LIMA_TZ).isoformat()


def _api_date_to_iso(value: str) -> str:
    return datetime.strptime(value, "%d/%m/%Y").date().isoformat()


def _normalize_supabase_job(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    return {
        "id": value.get("id"),
        "source": value.get("source", value.get("origen")),
        "start_date": value.get("start_date", value.get("fecha_inicio")),
        "end_date": value.get("end_date", value.get("fecha_fin")),
        "status": value.get("status", value.get("estado")),
        "stage": value.get("stage", value.get("etapa")),
        "progress": value.get("progress", value.get("progreso", 0)),
        "processed": value.get("processed", value.get("procesados", 0)),
        "total": value.get("total", 0),
        "message": value.get("message", value.get("mensaje", "")),
        "error": value.get("error"),
        "created_at": value.get("created_at", value.get("creado_en")),
        "started_at": value.get("started_at", value.get("iniciado_en")),
        "completed_at": value.get("completed_at", value.get("completado_en")),
        "already_running": bool(value.get("already_running", False)),
        "already_completed": bool(value.get("already_completed", False)),
    }


class CreditStore:
    def create_job(self, start_date: str, end_date: str, source: str) -> dict[str, Any]:
        raise NotImplementedError

    def update_progress(self, job_id: str, stage: str, progress: int, processed: int, total: int, message: str) -> None:
        raise NotImplementedError

    def complete_job(self, job_id: str, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def fail_job(self, job_id: str, error: str) -> None:
        raise NotImplementedError

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_active_job(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_result(self, job_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_accumulated(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def interrupt_running_jobs(self) -> None:
        raise NotImplementedError


@dataclass
class MemoryCreditStore(CreditStore):
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def create_job(self, start_date: str, end_date: str, source: str) -> dict[str, Any]:
        with self._lock:
            active = next((job for job in self.jobs.values() if job["status"] in {"queued", "running"}), None)
            if active:
                return {**deepcopy(active), "already_running": True}
            if source == "automatico":
                completed = next((
                    job for job in self.jobs.values()
                    if job["source"] == source
                    and job["start_date"] == start_date
                    and job["end_date"] == end_date
                    and job["status"] == "completed"
                ), None)
                if completed:
                    return {**deepcopy(completed), "already_completed": True}
            job_id = str(uuid.uuid4())
            job = {
                "id": job_id,
                "source": source,
                "start_date": start_date,
                "end_date": end_date,
                "status": "queued",
                "stage": "queued",
                "progress": 0,
                "processed": 0,
                "total": 0,
                "message": "Análisis en cola",
                "error": None,
                "created_at": _now_iso(),
                "started_at": None,
                "completed_at": None,
                "already_running": False,
                "already_completed": False,
            }
            self.jobs[job_id] = job
            return deepcopy(job)

    def update_progress(self, job_id: str, stage: str, progress: int, processed: int, total: int, message: str) -> None:
        with self._lock:
            job = self.jobs[job_id]
            job.update({
                "status": "running",
                "stage": stage,
                "progress": max(0, min(100, int(progress))),
                "processed": int(processed),
                "total": int(total),
                "message": message,
                "started_at": job["started_at"] or _now_iso(),
            })

    def complete_job(self, job_id: str, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        with self._lock:
            self.results[job_id] = {**deepcopy(summary), "prospectos": deepcopy(rows)}
            self.jobs[job_id].update({
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "processed": len(rows),
                "total": len(rows),
                "message": "Análisis crediticio completado",
                "completed_at": _now_iso(),
            })

    def fail_job(self, job_id: str, error: str) -> None:
        with self._lock:
            self.jobs[job_id].update({
                "status": "failed",
                "stage": "failed",
                "message": "El análisis crediticio no pudo completarse",
                "error": error,
                "completed_at": _now_iso(),
            })

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self.jobs.get(job_id)
            return deepcopy(job) if job else None

    def get_active_job(self) -> dict[str, Any] | None:
        with self._lock:
            job = next((item for item in self.jobs.values() if item["status"] in {"queued", "running"}), None)
            return deepcopy(job) if job else None

    def get_result(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            result = self.results.get(job_id)
            return deepcopy(result) if result else None

    def get_accumulated(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        start = datetime.strptime(start_date, "%d/%m/%Y").date()
        end = datetime.strptime(end_date, "%d/%m/%Y").date()
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        with self._lock:
            completed = sorted(self.jobs.values(), key=lambda item: item["created_at"])
            for job in completed:
                job_start = datetime.strptime(job["start_date"], "%d/%m/%Y").date()
                job_end = datetime.strptime(job["end_date"], "%d/%m/%Y").date()
                if job["status"] != "completed" or job_end < start or job_start > end:
                    continue
                for row in self.results.get(job["id"], {}).get("prospectos", []):
                    merged[(row.get("dni", ""), row.get("proyecto", ""))] = deepcopy(row)
        return list(merged.values())

    def interrupt_running_jobs(self) -> None:
        with self._lock:
            for job in self.jobs.values():
                if job["status"] in {"queued", "running"}:
                    job.update({
                        "status": "failed",
                        "stage": "failed",
                        "message": "Proceso interrumpido por reinicio del servidor",
                        "error": "Proceso interrumpido por reinicio del servidor",
                        "completed_at": _now_iso(),
                    })


@dataclass
class SupabaseCreditStore(CreditStore):
    url: str
    key: str

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _rpc(self, name: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> Any:
        response = requests.post(
            f"{self.url.rstrip('/')}/rest/v1/rpc/{name}",
            headers=self._headers(),
            json=payload or {},
            timeout=timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase RPC {name} failed: {response.status_code} {response.text}")
        if not response.content:
            return None
        return response.json()

    def create_job(self, start_date: str, end_date: str, source: str) -> dict[str, Any]:
        value = self._rpc("crediticio_crear_proceso", {
            "p_fecha_inicio": _api_date_to_iso(start_date),
            "p_fecha_fin": _api_date_to_iso(end_date),
            "p_origen": source,
        })
        return _normalize_supabase_job(value)

    def update_progress(self, job_id: str, stage: str, progress: int, processed: int, total: int, message: str) -> None:
        self._rpc("crediticio_actualizar_progreso", {
            "p_id": job_id,
            "p_etapa": stage,
            "p_progreso": int(progress),
            "p_procesados": int(processed),
            "p_total": int(total),
            "p_mensaje": message,
        })

    def complete_job(self, job_id: str, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        self._rpc("crediticio_completar_proceso", {
            "p_id": job_id,
            "p_resumen": summary,
            "p_prospectos": rows,
        }, timeout=180)

    def fail_job(self, job_id: str, error: str) -> None:
        self._rpc("crediticio_fallar_proceso", {"p_id": job_id, "p_error": error})

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return _normalize_supabase_job(self._rpc("crediticio_obtener_proceso", {"p_id": job_id}))

    def get_active_job(self) -> dict[str, Any] | None:
        return _normalize_supabase_job(self._rpc("crediticio_obtener_activo"))

    def get_result(self, job_id: str) -> dict[str, Any] | None:
        return self._rpc("crediticio_obtener_resultado", {"p_id": job_id}, timeout=120)

    def get_accumulated(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        value = self._rpc("crediticio_consultar_acumulado", {
            "p_fecha_inicio": _api_date_to_iso(start_date),
            "p_fecha_fin": _api_date_to_iso(end_date),
        }, timeout=120)
        return value or []

    def interrupt_running_jobs(self) -> None:
        self._rpc("crediticio_interrumpir_procesos")


def build_credit_store() -> CreditStore:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        return SupabaseCreditStore(url=url, key=key)
    return MemoryCreditStore()
