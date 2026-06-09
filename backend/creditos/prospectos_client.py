"""Cliente Evolta para Gestión Seguimiento y perfil crediticio Experian."""
from __future__ import annotations

import time
from typing import Any

import requests

BASE = "https://v4.evolta.pe"
_SEGUIMIENTO_PAGE = f"{BASE}/Seguimiento/BuscadorPersona/Index?Tipo=1"
_VALIDA_SESION_URL = f"{BASE}/Comercial/OperacionComercial/ValidaSesion"
_LOGIN_URL = f"{BASE}/Login/Acceso/Logearse"
_BUSCAR_PERSONAS_URL = f"{BASE}/Seguimiento/BuscadorPersona/GetBuscarPersonas/"
_EXPERIAN_URL = f"{BASE}/SistemasExternos/IntegracionTerceros/GetUltimoHistorialExperian"

_XHR_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


class EvoltaProspectosClient:
    def __init__(self, evolta_user: str, evolta_pass: str) -> None:
        self._user = evolta_user
        self._pass = evolta_pass
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Origin": BASE,
            "Referer": _SEGUIMIENTO_PAGE,
        })

    def login(self) -> None:
        resp = self.session.post(
            _LOGIN_URL,
            json={
                "usuario": self._user,
                "clave": self._pass,
                "ipInfo": '{"usuario":"hola"}',
            },
            timeout=30,
        )
        resp.raise_for_status()
        try:
            redirect = resp.json()
            if isinstance(redirect, str) and redirect.startswith("/"):
                self.session.get(f"{BASE}{redirect}", timeout=30)
        except Exception:
            pass

    def _valida_sesion(self) -> None:
        self.session.post(
            _VALIDA_SESION_URL,
            data="",
            headers={
                **_XHR_HEADERS,
                "Content-Type": "application/json; charset=utf-8",
                "Referer": _SEGUIMIENTO_PAGE,
            },
            timeout=30,
        )

    def prepare_session(self) -> None:
        self.session.get(_SEGUIMIENTO_PAGE, timeout=30)
        self._valida_sesion()

    def buscar_prospectos(
        self,
        fecha_inicio: str,
        fecha_fin: str,
        id_proyecto: int | str = "0",
        estado: str = "0",
        tipo_fecha: str = "1",
        rows: int = 9999,
    ) -> list[dict[str, Any]]:
        form_data = {
            "TipoPersona": "2",
            "Nombres": "",
            "NroDocumento": "",
            "IdEstado": estado,
            "IdListaCarga": "0",
            "IdUsuarioAsignado": "0",
            "Tipo": "1",
            "FechaInicio": fecha_inicio,
            "fechaFin": fecha_fin,
            "TipoFecha": tipo_fecha,
            "idProyecto": str(id_proyecto),
            "IdFormaPago": "",
            "IdNivelIngresos": "",
            "IdPerfilCrediticio": "",
            "IdNiveInteres": "",  # typo intencional de Evolta
            "IdFormaContacto": "",
            "Vencido": "false",
            "ConScore": "false",
            "NuevoProspectoAsignado": "false",
            "IdComoSeEntero": "",
            "IdUltimoProyecto": "0",
            "_search": "false",
            "nd": str(int(time.time() * 1000)),
            "rows": str(rows),
            "page": "1",
            "sidx": "Nombre",
            "sord": "asc",
        }

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self.session.post(
                    _BUSCAR_PERSONAS_URL,
                    data=form_data,
                    headers={
                        **_XHR_HEADERS,
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "Referer": _SEGUIMIENTO_PAGE,
                    },
                    timeout=180,
                    allow_redirects=False,
                )
                break
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
        else:
            raise last_exc

        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location", "")
            raise RuntimeError(
                f"GetBuscarPersonas redirigido inesperadamente → {loc}. "
                "Revisar endpoint o parámetros."
            )

        resp.raise_for_status()
        if not resp.content.strip():
            return []

        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(
                f"GetBuscarPersonas devolvió respuesta no JSON: {resp.text[:300]}"
            ) from exc

        return data.get("rows", [])

    def get_ultimo_historial_experian(self, nro_doc: str, tipo_doc: int = 1) -> dict[str, Any] | None:
        resp = self.session.get(
            _EXPERIAN_URL,
            params={"TipoDoc": str(tipo_doc), "NroDoc": nro_doc},
            headers={
                **_XHR_HEADERS,
                "Referer": _SEGUIMIENTO_PAGE,
            },
            timeout=30,
        )
        resp.raise_for_status()
        if not resp.content.strip():
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        if isinstance(data, list):
            return data[0] if data else None
        if not data or data.get("Id", 0) == 0:
            return None
        return data
