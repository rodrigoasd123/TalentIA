"""Medicion HTTP acotada y minimizada para el piloto local."""

from __future__ import annotations

import math
import statistics
import time
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from itertools import repeat
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class ResultadoSolicitud:
    exito: bool
    duracion_ms: float
    tipo_error: str | None = None


@dataclass(frozen=True, slots=True)
class ResumenRendimiento:
    solicitudes: int
    exitos: int
    errores: int
    promedio_ms: float
    p50_ms: float
    p95_ms: float
    errores_por_tipo: dict[str, int]

    def como_dict(self) -> dict[str, object]:
        return asdict(self)


def _percentil(valores: Sequence[float], proporcion: float) -> float:
    """Calcula nearest-rank sobre una muestra no vacia."""
    ordenados = sorted(valores)
    indice = max(0, math.ceil(proporcion * len(ordenados)) - 1)
    return ordenados[indice]


def validar_parametros(url: str, solicitudes: int, concurrencia: int, timeout: float) -> None:
    partes = urlsplit(url)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        raise ValueError("La URL debe ser HTTP o HTTPS y contener un host")
    if not 1 <= solicitudes <= 10_000:
        raise ValueError("Las solicitudes deben estar entre 1 y 10000")
    if not 1 <= concurrencia <= min(solicitudes, 100):
        raise ValueError("La concurrencia debe estar entre 1 y min(solicitudes, 100)")
    if not 0 < timeout <= 120:
        raise ValueError("El timeout debe ser mayor que 0 y menor o igual que 120 segundos")


def medir_solicitud(url: str, timeout: float) -> ResultadoSolicitud:
    inicio = time.perf_counter()
    try:
        solicitud = Request(  # noqa: S310 - el esquema fue validado antes de abrir la URL
            url, method="GET", headers={"User-Agent": "TalentIA-Pilot-Probe/1"}
        )
        with urlopen(solicitud, timeout=timeout) as respuesta:  # noqa: S310
            estado = int(respuesta.status)
        exito = 200 <= estado < 400
        tipo_error = None if exito else f"http_{estado}"
    except HTTPError as error:
        exito = False
        tipo_error = f"http_{error.code}"
    except TimeoutError:
        exito = False
        tipo_error = "timeout"
    except (URLError, OSError):
        exito = False
        tipo_error = "conexion"
    duracion_ms = (time.perf_counter() - inicio) * 1000
    return ResultadoSolicitud(exito, duracion_ms, tipo_error)


def resumir_resultados(resultados: Sequence[ResultadoSolicitud]) -> ResumenRendimiento:
    if not resultados:
        raise ValueError("Se requiere al menos un resultado")
    latencias = [resultado.duracion_ms for resultado in resultados]
    exitos = sum(resultado.exito for resultado in resultados)
    errores = Counter(
        resultado.tipo_error for resultado in resultados if resultado.tipo_error is not None
    )
    return ResumenRendimiento(
        solicitudes=len(resultados),
        exitos=exitos,
        errores=len(resultados) - exitos,
        promedio_ms=round(statistics.fmean(latencias), 3),
        p50_ms=round(_percentil(latencias, 0.50), 3),
        p95_ms=round(_percentil(latencias, 0.95), 3),
        errores_por_tipo=dict(sorted(errores.items())),
    )


def ejecutar_medicion(
    url: str, solicitudes: int = 20, concurrencia: int = 4, timeout: float = 5.0
) -> ResumenRendimiento:
    validar_parametros(url, solicitudes, concurrencia, timeout)
    with ThreadPoolExecutor(max_workers=concurrencia) as ejecutor:
        resultados = list(
            ejecutor.map(medir_solicitud, repeat(url, solicitudes), repeat(timeout, solicitudes))
        )
    return resumir_resultados(resultados)
