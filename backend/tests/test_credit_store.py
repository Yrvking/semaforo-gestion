import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from creditos.store import MemoryCreditStore  # noqa: E402


class MemoryCreditStoreTests(unittest.TestCase):
    def test_job_lifecycle_keeps_progress_separate_from_general_sync(self):
        store = MemoryCreditStore()
        job = store.create_job("01/06/2026", "09/06/2026", "manual")

        store.update_progress(job["id"], "experian", 60, 3, 5, "Consultando perfiles")
        current = store.get_job(job["id"])

        self.assertEqual("running", current["status"])
        self.assertEqual("experian", current["stage"])
        self.assertEqual(60, current["progress"])
        self.assertEqual(3, current["processed"])
        self.assertEqual(5, current["total"])

    def test_completed_job_exposes_summary_and_rows(self):
        store = MemoryCreditStore()
        job = store.create_job("09/06/2026", "09/06/2026", "automatico")
        rows = [{"dni": "12345678", "proyecto": "SUNNY", "tiene_score": True}]
        summary = {"total": 1, "con_score": 1, "sin_score": 0, "resumen_por_proyecto": []}

        store.complete_job(job["id"], summary, rows)

        self.assertEqual("completed", store.get_job(job["id"])["status"])
        self.assertEqual(rows, store.get_result(job["id"])["prospectos"])

    def test_active_job_prevents_second_credit_process(self):
        store = MemoryCreditStore()
        first = store.create_job("01/06/2026", "09/06/2026", "manual")

        second = store.create_job("09/06/2026", "09/06/2026", "automatico")

        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["already_running"])

    def test_completed_automatic_day_is_not_created_twice(self):
        store = MemoryCreditStore()
        first = store.create_job("09/06/2026", "09/06/2026", "automatico")
        store.complete_job(first["id"], {"total": 0}, [])

        second = store.create_job("09/06/2026", "09/06/2026", "automatico")

        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["already_completed"])

    def test_accumulated_results_merge_completed_days_without_duplicate_people(self):
        store = MemoryCreditStore()
        first = store.create_job("08/06/2026", "08/06/2026", "automatico")
        store.complete_job(first["id"], {"total": 1}, [
            {"dni": "12345678", "proyecto": "SUNNY", "score": 700, "tiene_score": True}
        ])
        second = store.create_job("09/06/2026", "09/06/2026", "automatico")
        store.complete_job(second["id"], {"total": 2}, [
            {"dni": "12345678", "proyecto": "SUNNY", "score": 750, "tiene_score": True},
            {"dni": "87654321", "proyecto": "LITORAL 900", "tiene_score": False},
        ])

        rows = store.get_accumulated("08/06/2026", "09/06/2026")

        self.assertEqual(2, len(rows))
        self.assertEqual(750, next(row for row in rows if row["dni"] == "12345678")["score"])


if __name__ == "__main__":
    unittest.main()
