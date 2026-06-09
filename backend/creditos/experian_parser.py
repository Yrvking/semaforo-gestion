"""Parsea el campo RespuestaProveedor de GetUltimoHistorialExperian."""
from __future__ import annotations

import json
import re
from typing import Any

_SEMA_MAP = {"V": "Verde", "A": "Amarillo", "R": "Rojo", "N": "Negro"}


def _parse_calificativo(texto: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for cat in ("NOR", "CPP", "DEF", "DUD", "PER"):
        m = re.search(rf"{cat}\s+([\d.]+)%", texto)
        result[cat] = float(m.group(1)) if m else 0.0
    return result


def parse_experian(respuesta_proveedor: str | None) -> dict[str, Any] | None:
    """Extrae los campos clave de RespuestaProveedor. Retorna None si no hay datos."""
    if not respuesta_proveedor or not respuesta_proveedor.strip():
        return None
    try:
        data = json.loads(respuesta_proveedor.strip())
    except (json.JSONDecodeError, ValueError):
        return None

    resumen = data.get("ConRap", {}).get("Resumen_ConRap", {})
    sabio = data.get("Sabio", {})
    inf_bas = data.get("InfBas", {})

    calificativo = resumen.get("Calificativo", "")
    cal = _parse_calificativo(calificativo)

    semaforos = resumen.get("Semaforos", "")
    sema_char = semaforos[-1] if semaforos else ""

    motivos = sabio.get("Motivos") or []

    return {
        "score": sabio.get("ScoreSabio"),
        "nivel_score": sabio.get("NivSco", ""),
        "resultado": sabio.get("Resul", ""),
        "capacidad_pago": sabio.get("CapacidadPago", ""),
        "motivos": "; ".join(str(m) for m in motivos),
        "fecha_evaluacion": resumen.get("FechaProceso", ""),
        "deuda_total": _to_float(resumen.get("DeudaTotal")),
        "calificativo": calificativo,
        "nor_pct": cal["NOR"],
        "cpp_pct": cal["CPP"],
        "def_pct": cal["DEF"],
        "dud_pct": cal["DUD"],
        "per_pct": cal["PER"],
        "nro_bancos": _to_int(resumen.get("NroEntFin")),
        "deuda_tributaria": _to_float(resumen.get("DeudaTributaria")),
        "deuda_laboral": _to_float(resumen.get("DeudaLaboral")),
        "semaforo_actual": _SEMA_MAP.get(sema_char, sema_char),
        "nombre_completo": inf_bas.get("RazSoc", ""),
        "estado_fiscal": inf_bas.get("EstCon", ""),
        "estado_domicilio": inf_bas.get("EstDom", ""),
    }


def _to_float(v: Any) -> float:
    try:
        return float(v or 0)
    except (ValueError, TypeError):
        return 0.0


def _to_int(v: Any) -> int:
    try:
        return int(v or 0)
    except (ValueError, TypeError):
        return 0
