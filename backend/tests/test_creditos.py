import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402
from creditos.experian_parser import parse_experian  # noqa: E402


class ExperianParserTests(unittest.TestCase):
    def test_parse_experian_extracts_score_debt_and_risk_percentages(self):
        payload = json.dumps({
            "ConRap": {
                "Resumen_ConRap": {
                    "Calificativo": "NOR 85.5% CPP 10% DEF 2% DUD 1.5% PER 1%",
                    "Semaforos": "V",
                    "FechaProceso": "09/06/2026",
                    "DeudaTotal": "12345.67",
                    "NroEntFin": "3",
                }
            },
            "Sabio": {
                "ScoreSabio": 742,
                "NivSco": "MEDIO",
                "Resul": "CUMPLE",
                "CapacidadPago": "2500",
                "Motivos": ["Historial estable", "Sin mora"],
            },
            "InfBas": {"RazSoc": "Persona Demo"},
        })

        parsed = parse_experian(payload)

        self.assertEqual(742, parsed["score"])
        self.assertEqual(12345.67, parsed["deuda_total"])
        self.assertEqual(85.5, parsed["nor_pct"])
        self.assertEqual(10.0, parsed["cpp_pct"])
        self.assertEqual("Verde", parsed["semaforo_actual"])
        self.assertEqual("Historial estable; Sin mora", parsed["motivos"])

    def test_parse_experian_returns_none_for_invalid_json(self):
        self.assertIsNone(parse_experian("not-json"))


class CreditEndpointTests(unittest.TestCase):
    def test_rejects_inverted_date_range(self):
        request = main.CreditAnalysisRequest(
            start_date="10/06/2026",
            end_date="09/06/2026",
        )

        with self.assertRaises(HTTPException) as context:
            main.iniciar_analisis_credito(request)

        self.assertEqual(400, context.exception.status_code)

    def test_starts_background_job_and_returns_identifier(self):
        request = main.CreditAnalysisRequest(
            start_date="01/06/2026",
            end_date="09/06/2026",
        )
        expected = {"id": "job-1", "status": "queued", "already_running": False}

        with patch.object(main.credit_job_service, "start", return_value=expected) as start:
            result = main.iniciar_analisis_credito(request)

        self.assertEqual(expected, result)
        start.assert_called_once_with("01/06/2026", "09/06/2026", "manual")

    def test_daily_job_processes_previous_lima_day(self):
        with patch.object(main.credit_job_service, "start") as start:
            main.run_daily_credit_job(today=date(2026, 6, 10))

        start.assert_called_once_with("09/06/2026", "09/06/2026", "automatico")


if __name__ == "__main__":
    unittest.main()
