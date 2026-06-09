from __future__ import annotations

import logging
import threading
from collections import Counter
from typing import Any, Callable

from .store import CreditStore


logger = logging.getLogger(__name__)


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    con_score = sum(1 for row in rows if row.get("tiene_score"))
    projects = Counter((row.get("proyecto") or "SIN PROYECTO") for row in rows)
    return {
        "total": total,
        "con_score": con_score,
        "sin_score": total - con_score,
        "resumen_por_proyecto": [
            {"proyecto": project, "total": count}
            for project, count in sorted(projects.items())
        ],
    }


class CreditJobService:
    def __init__(
        self,
        store: CreditStore,
        extractor: Callable[..., list[dict[str, Any]]],
        credentials: Callable[[], tuple[str, str]],
    ) -> None:
        self.store = store
        self.extractor = extractor
        self.credentials = credentials

    def start(self, start_date: str, end_date: str, source: str, background: bool = True) -> dict[str, Any]:
        job = self.store.create_job(start_date, end_date, source)
        if job.get("already_running") or job.get("already_completed"):
            return job
        if background:
            thread = threading.Thread(
                target=self.run,
                args=(job["id"], start_date, end_date, source),
                daemon=True,
                name=f"credit-job-{job['id'][:8]}",
            )
            thread.start()
        else:
            self.run(job["id"], start_date, end_date, source)
        return self.store.get_job(job["id"]) or job

    def run(self, job_id: str, start_date: str, end_date: str, source: str) -> None:
        try:
            self.store.update_progress(job_id, "login", 2, 0, 0, "Conectando con Evolta")
            user, password = self.credentials()
            rows = self.extractor(
                user=user,
                password=password,
                fecha_inicio=start_date,
                fecha_fin=end_date,
                tipos_fecha=("1",) if source == "automatico" else ("1", "2"),
                progress_callback=lambda stage, progress, processed, total, message: self.store.update_progress(
                    job_id, stage, progress, processed, total, message
                ),
            )
            self.store.update_progress(job_id, "saving", 97, len(rows), len(rows), "Guardando resultados")
            self.store.complete_job(job_id, build_summary(rows), rows)
        except Exception as exc:
            logger.exception("Credit job %s failed", job_id)
            self.store.fail_job(job_id, str(exc))
