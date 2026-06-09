import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from creditos.jobs import CreditJobService  # noqa: E402
from creditos.store import MemoryCreditStore  # noqa: E402


class CreditJobServiceTests(unittest.TestCase):
    def test_runner_persists_progress_and_summary(self):
        store = MemoryCreditStore()

        def extractor(**kwargs):
            callback = kwargs["progress_callback"]
            callback("prospectos", 30, 2, 4, "Leyendo prospectos")
            callback("experian", 75, 3, 4, "Consultando Experian")
            return [
                {"proyecto": "SUNNY", "tiene_score": True},
                {"proyecto": "SUNNY", "tiene_score": False},
            ]

        service = CreditJobService(store=store, extractor=extractor, credentials=lambda: ("u", "p"))
        job = service.start("01/06/2026", "09/06/2026", "manual", background=False)

        status = store.get_job(job["id"])
        result = store.get_result(job["id"])
        self.assertEqual("completed", status["status"])
        self.assertEqual(100, status["progress"])
        self.assertEqual(2, result["total"])
        self.assertEqual(1, result["con_score"])

    def test_automatic_job_uses_registration_date_only(self):
        store = MemoryCreditStore()
        captured = {}

        def extractor(**kwargs):
            captured.update(kwargs)
            return []

        service = CreditJobService(store=store, extractor=extractor, credentials=lambda: ("u", "p"))
        service.start("09/06/2026", "09/06/2026", "automatico", background=False)

        self.assertEqual(("1",), captured["tipos_fecha"])


if __name__ == "__main__":
    unittest.main()
