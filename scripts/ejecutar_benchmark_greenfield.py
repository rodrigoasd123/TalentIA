"""Ejecuta el benchmark sintetico local y registra la corrida en MLflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from talentia.ai.evaluacion_referencia import ejecutar_benchmark


def main() -> None:
    analizador = argparse.ArgumentParser()
    analizador.add_argument(
        "--corpus",
        type=Path,
        default=Path("tests/golden/corpus_cv_anonimizado.json"),
    )
    analizador.add_argument(
        "--tracking-uri",
        default=os.getenv("TALENTIA_MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"),
    )
    argumentos = analizador.parse_args()
    resultado = ejecutar_benchmark(
        argumentos.corpus,
        tracking_uri=argumentos.tracking_uri,
        ubicacion_artefactos=Path("mlruns").resolve().as_uri(),
    )
    print(json.dumps(resultado, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
