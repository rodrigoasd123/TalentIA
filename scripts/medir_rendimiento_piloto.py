"""Mide de forma acotada la latencia HTTP del piloto TalentIA."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from talentia.platform.observabilidad.rendimiento import ejecutar_medicion


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/health")
    parser.add_argument("--solicitudes", type=int, default=20)
    parser.add_argument("--concurrencia", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argumentos = crear_parser().parse_args(argv)
    try:
        resumen = ejecutar_medicion(
            argumentos.url,
            solicitudes=argumentos.solicitudes,
            concurrencia=argumentos.concurrencia,
            timeout=argumentos.timeout,
        )
    except ValueError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(resumen.como_dict(), ensure_ascii=False, sort_keys=True))
    return 1 if resumen.errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
