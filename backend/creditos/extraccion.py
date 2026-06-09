"""Orquesta la extracción de prospectos + perfiles crediticios para 5 proyectos."""
from __future__ import annotations

import re
import time
from datetime import date
from typing import Any, Callable

from .experian_parser import parse_experian
from .prospectos_client import EvoltaProspectosClient


TIPOS_FECHA: list[tuple[str, str]] = [
    ("1", "Registro"),
    ("2", "Último Contacto"),
]

PROYECTOS_OBJETIVO: dict[str, int] = {
    "DOMINGO ORUE": 2555,
    "HELIO - SANTA BEATRIZ": 2015,
    "LITORAL 900": 1894,
    "SUNNY": 2229,
    "LOMAS DE CARABAYLLO": 65,
}


def _strip_html(text: str) -> str:
    import html as _html

    text = _html.unescape(str(text))
    text = re.sub(r"<[^>]*>", "", text, flags=re.DOTALL)
    for sep in ("span>", "Correo:", "Telefono:", "Comentarios:"):
        idx = text.find(sep)
        if idx > 0:
            text = text[:idx]
    return text.strip()


def _normalize_row(row: dict[str, Any], proyecto: str) -> dict[str, Any]:
    cell = row.get("cell", [])

    def c(i: int) -> str:
        return str(cell[i]).strip() if i < len(cell) else ""

    return {
        "id_persona": str(row.get("id", "")),
        "nombre": _strip_html(c(0)),
        "dni": c(1),
        "proyecto": proyecto,
        "celular": c(4),
        "email": c(5),
        "fecha_registro": c(6),
        "estado": c(8),
        "responsable": c(9),
        "tiene_score": False,
        "nombre_completo": "",
        "score": None,
        "nivel_score": "",
        "resultado": "",
        "capacidad_pago": "",
        "motivos": "",
        "fecha_evaluacion": "",
        "deuda_total": 0.0,
        "calificativo": "",
        "nor_pct": 0.0,
        "cpp_pct": 0.0,
        "def_pct": 0.0,
        "dud_pct": 0.0,
        "per_pct": 0.0,
        "nro_bancos": 0,
        "deuda_tributaria": 0.0,
        "deuda_laboral": 0.0,
        "semaforo_actual": "",
        "estado_fiscal": "",
        "estado_domicilio": "",
        "tipo_fecha": "",
    }


def extraer(
    user: str,
    password: str,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    tipos_fecha: tuple[str, ...] = ("1", "2"),
    progress_callback: Callable[[str, int, int, int, str], None] | None = None,
) -> list[dict[str, Any]]:
    hoy = date.today()
    fecha_fin = fecha_fin or hoy.strftime("%d/%m/%Y")
    fecha_inicio = fecha_inicio or hoy.replace(day=1).strftime("%d/%m/%Y")

    client = EvoltaProspectosClient(user, password)
    client.login()
    client.prepare_session()

    def report(stage: str, progress: int, processed: int, total: int, message: str) -> None:
        if progress_callback:
            progress_callback(stage, progress, processed, total, message)

    estados_objetivo = ["2", "3"]

    por_dni: dict[str, dict[str, Any]] = {}
    tipo_fecha_por_dni: dict[str, set[str]] = {}

    selected_types = [item for item in TIPOS_FECHA if item[0] in tipos_fecha]
    search_total = len(PROYECTOS_OBJETIVO) * len(estados_objetivo) * len(selected_types)
    search_current = 0

    for nombre, pid in PROYECTOS_OBJETIVO.items():
        try:
            for estado in estados_objetivo:
                for tf_val, tf_label in selected_types:
                    rows = client.buscar_prospectos(
                        fecha_inicio,
                        fecha_fin,
                        pid,
                        estado=estado,
                        tipo_fecha=tf_val,
                    )
                    for row in rows:
                        p = _normalize_row(row, nombre)
                        if not p["dni"]:
                            continue
                        tipo_fecha_por_dni.setdefault(p["dni"], set()).add(tf_label)
                        if p["dni"] not in por_dni:
                            por_dni[p["dni"]] = p
                    search_current += 1
                    report(
                        "prospectos",
                        5 + round((search_current / max(search_total, 1)) * 30),
                        search_current,
                        search_total,
                        f"Leyendo prospectos de {nombre}",
                    )
                    time.sleep(0.2)
        except Exception:
            search_current += len(estados_objetivo) * len(selected_types)
            continue
        time.sleep(0.3)

    for dni, p in por_dni.items():
        tipos = tipo_fecha_por_dni.get(dni, set())
        if len(tipos) >= 2:
            p["tipo_fecha"] = "Ambos"
        elif "Último Contacto" in tipos:
            p["tipo_fecha"] = "Último Contacto"
        else:
            p["tipo_fecha"] = "Registro"

    total_profiles = len(por_dni)
    for index, (_, p) in enumerate(por_dni.items(), 1):
        try:
            historial = client.get_ultimo_historial_experian(p["dni"])
            if historial and historial.get("RespuestaProveedor"):
                parsed = parse_experian(historial["RespuestaProveedor"])
                if parsed:
                    p.update(parsed)
                    p["tiene_score"] = True
        except Exception:
            continue
        finally:
            report(
                "experian",
                35 + round((index / max(total_profiles, 1)) * 60),
                index,
                total_profiles,
                f"Consultando perfiles Experian ({index}/{total_profiles})",
            )
        time.sleep(0.2)

    return list(por_dni.values())
