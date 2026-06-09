import json
import os
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd


LIMA_TZ = ZoneInfo("America/Lima")


def lima_today() -> date:
    return datetime.now(LIMA_TZ).date()

TARGET_PROJECTS = [
    "HELIO - SANTA BEATRIZ",
    "LITORAL 900",
    "LOMAS DE CARABAYLLO",
    "SUNNY",
    "DOMINGO ORUE",
]


@dataclass(frozen=True)
class ReportDefinition:
    prefix: str
    required_columns: Sequence[str]
    primary_date_columns: Sequence[str]


REPORT_DEFINITIONS: Dict[str, ReportDefinition] = {
    "reporteProspectos": ReportDefinition(
        prefix="reporteProspectos",
        required_columns=(
            "Proyecto",
            "TipoInmueble",
            "LeadUnicoxMesProyecto",
            "ComoSeEntero",
            "SubEstado",
            "FechaRegistro",
        ),
        primary_date_columns=("FechaRegistro",),
    ),
    "ReporteVenta": ReportDefinition(
        prefix="ReporteVenta",
        required_columns=("Proyecto", "TipoInmueble_1", "FechaVenta"),
        primary_date_columns=("FechaVenta",),
    ),
    "Separacion": ReportDefinition(
        prefix="Separacion",
        required_columns=("DescripcionProyecto", "TipoInmueble_1", "FechaSepDef"),
        primary_date_columns=("FechaSepDef", "FechaSepTemp", "FechaRegistro"),
    ),
    "ReporteVisitas": ReportDefinition(
        prefix="ReporteVisitas",
        required_columns=(
            "Proyecto",
            "TipoInmueble",
            "VisitaUnicaxMesProyecto",
            "FechaVisita",
        ),
        primary_date_columns=("FechaVisita",),
    ),
}


class ReportValidationError(RuntimeError):
    pass


class ReportValidationResult(dict):
    def __init__(self, start_date: date, end_date: date):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date


def _find_report_file(directory: Path, prefix: str) -> Path:
    matches = []
    for extension in (".xlsx", ".xls", ".csv"):
        matches.extend(directory.glob(f"{prefix}*{extension}"))
    matches = [path for path in matches if path.is_file()]
    if not matches:
        raise ReportValidationError(f"Falta el reporte requerido: {prefix}")
    return max(matches, key=lambda path: path.stat().st_mtime)


def _load_dataframe(path: Path) -> pd.DataFrame:
    try:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        if path.suffix.lower() == ".xlsx":
            return pd.read_excel(path, engine="openpyxl")
        return pd.read_excel(path)
    except Exception as exc:
        raise ReportValidationError(f"No se pudo abrir {path.name}: {exc}") from exc


def _primary_dates(
    df: pd.DataFrame, definition: ReportDefinition, report_name: str
) -> tuple[pd.Timestamp, pd.Timestamp]:
    available = [column for column in definition.primary_date_columns if column in df.columns]
    if not available:
        expected = ", ".join(definition.primary_date_columns)
        raise ReportValidationError(
            f"{report_name}: no se encontro una columna de fecha primaria ({expected})"
        )

    parsed = pd.to_datetime(df[available[0]], dayfirst=True, errors="coerce")
    parsed = parsed.dropna()
    if parsed.empty:
        raise ReportValidationError(
            f"{report_name}: la columna {available[0]} no contiene fechas validas"
        )
    return parsed.min(), parsed.max()


def validate_report_set(
    directory: str | Path, start_date: date, end_date: date
) -> ReportValidationResult:
    directory = Path(directory)
    if start_date > end_date:
        raise ReportValidationError("El inicio del periodo no puede ser posterior al fin")

    validation = ReportValidationResult(start_date, end_date)
    for name, definition in REPORT_DEFINITIONS.items():
        path = _find_report_file(directory, definition.prefix)
        df = _load_dataframe(path)
        df.columns = df.columns.astype(str).str.strip()

        if df.empty:
            raise ReportValidationError(f"{name}: el reporte esta sin filas")

        missing = [column for column in definition.required_columns if column not in df.columns]
        if missing:
            raise ReportValidationError(
                f"{name}: faltan columnas requeridas: {', '.join(missing)}"
            )

        min_date, max_date = _primary_dates(df, definition, name)
        if min_date.date() < start_date or max_date.date() > end_date:
            raise ReportValidationError(
                f"{name}: fechas fuera del periodo {start_date.isoformat()} a "
                f"{end_date.isoformat()} ({min_date.date()} a {max_date.date()})"
            )

        validation[name] = {
            "source_path": str(path),
            "filename": f"{definition.prefix}{path.suffix.lower()}",
            "rows": int(len(df)),
            "bytes": int(path.stat().st_size),
            "date_min": min_date.date().isoformat(),
            "date_max": max_date.date().isoformat(),
        }

    return validation


def _active_report_files(active_dir: Path) -> Iterable[Path]:
    for definition in REPORT_DEFINITIONS.values():
        for extension in (".xlsx", ".xls", ".csv"):
            yield from active_dir.glob(f"{definition.prefix}*{extension}")


def iter_downloadable_files(active_dir: str | Path) -> Iterable[Path]:
    active_dir = Path(active_dir)
    yielded = set()
    for path in _active_report_files(active_dir):
        if path.parent == active_dir and path.name not in yielded:
            yielded.add(path.name)
            yield path
    manifest = active_dir / "manifest.json"
    if manifest.exists():
        yield manifest


def _restore_backup(active_dir: Path, backup_dir: Path) -> None:
    for path in list(_active_report_files(active_dir)):
        path.unlink(missing_ok=True)
    (active_dir / "manifest.json").unlink(missing_ok=True)
    for path in backup_dir.iterdir():
        if path.name == "backup_manifest.json":
            continue
        shutil.copy2(path, active_dir / path.name)


def publish_report_set(
    staging_dir: str | Path,
    active_dir: str | Path,
    validation: Mapping[str, Mapping[str, object]],
    goals: Mapping[str, Mapping[str, int]] | None = None,
) -> dict:
    staging_dir = Path(staging_dir)
    active_dir = Path(active_dir)
    active_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(LIMA_TZ)
    backup_dir = active_dir / "backups" / now.strftime("%Y%m%d_%H%M%S_%f")
    backup_dir.mkdir(parents=True, exist_ok=False)

    current_files = list(_active_report_files(active_dir))
    for optional_name in ("meta_data.json", "manifest.json"):
        optional_path = active_dir / optional_name
        if optional_path.exists():
            current_files.append(optional_path)
    for path in current_files:
        shutil.copy2(path, backup_dir / path.name)

    requested_start = getattr(validation, "start_date", None)
    requested_end = getattr(validation, "end_date", None)
    manifest = {
        "published_at": now.isoformat(),
        "period": {
            "start": (
                requested_start.isoformat()
                if requested_start
                else min(item["date_min"] for item in validation.values())
            ),
            "end": (
                requested_end.isoformat()
                if requested_end
                else max(item["date_max"] for item in validation.values())
            ),
        },
        "reports": {
            name: {key: value for key, value in item.items() if key != "source_path"}
            for name, item in validation.items()
        },
        "goals": goals or {},
    }

    pending_paths = []
    try:
        for name, item in validation.items():
            source = Path(str(item["source_path"]))
            target_name = str(item["filename"])
            pending = active_dir / f".{target_name}.publishing"
            shutil.copy2(source, pending)
            pending_paths.append((pending, active_dir / target_name, name))

        manifest_pending = active_dir / ".manifest.json.publishing"
        manifest_pending.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        for pending, target, name in pending_paths:
            for existing in list(_active_report_files(active_dir)):
                if existing.name.startswith(REPORT_DEFINITIONS[name].prefix) and existing != target:
                    existing.unlink(missing_ok=True)
            os.replace(pending, target)
        os.replace(manifest_pending, active_dir / "manifest.json")
    except Exception:
        for pending, _, _ in pending_paths:
            pending.unlink(missing_ok=True)
        (active_dir / ".manifest.json.publishing").unlink(missing_ok=True)
        _restore_backup(active_dir, backup_dir)
        raise

    (backup_dir / "backup_manifest.json").write_text(
        json.dumps(
            {
                "created_at": now.isoformat(),
                "files": sorted(path.name for path in current_files),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"backup_dir": str(backup_dir), "manifest": manifest}
