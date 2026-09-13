"""Benchmark reproducible de AG-02 y AG-03 con corpus sintetico."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from talentia.ai.agents.evaluador import evaluar
from talentia.ai.agents.lector_cv import extraer_cv_paginas
from talentia.ai.guardrails.privacidad import sanitizar
from talentia.modules.recruitment.domain.modelos import RequisitoPerfil

ProveedorBenchmark = Callable[[str], dict[str, object]]


def _termino_habilidad(texto: str) -> str:
    segmento = texto.split("Habilidades:", 1)[-1]
    return segmento.split(",", 1)[0].strip().split()[0]


def evaluar_corpus(
    corpus: list[dict[str, str]], proveedor: ProveedorBenchmark | None = None
) -> dict[str, object]:
    extracciones = 0
    evaluaciones_con_evidencia = 0
    combinadas = 0
    for caso in corpus:
        texto = caso["texto"]
        limpio = sanitizar(texto)
        if proveedor is not None:
            proveedor(limpio.texto)
        lectura = extraer_cv_paginas(caso["id"], ((1, texto),))
        campos_extraidos = [campo for campo in lectura.campos if campo.valor is not None]
        extraccion_correcta = len(campos_extraidos) >= 2
        extracciones += int(extraccion_correcta)
        termino = _termino_habilidad(texto)
        requisito = RequisitoPerfil("HAB", termino, True, Decimal("1"))
        evaluacion = evaluar(caso["id"], texto, (requisito,))
        tiene_evidencia = bool(evaluacion.resultados[0].evidencia)
        evaluaciones_con_evidencia += int(tiene_evidencia)
        combinadas += int(extraccion_correcta and tiene_evidencia)
    total = len(corpus)
    contenido = json.dumps(corpus, sort_keys=True, ensure_ascii=True).encode()
    return {
        "dataset_sha256": hashlib.sha256(contenido).hexdigest(),
        "casos": total,
        "ag_02_tasa_extraccion": extracciones / total if total else 0.0,
        "ag_03_tasa_evidencia": evaluaciones_con_evidencia / total if total else 0.0,
        "flujo_tasa_combinada": combinadas / total if total else 0.0,
        "proveedor": "doble_controlado" if proveedor else "local_determinista",
        "version_configuracion": "greenfield-v1",
    }


def ejecutar_benchmark(
    ruta_corpus: Path,
    *,
    tracking_uri: str | None = None,
    experimento: str = "talentia-greenfield",
    ubicacion_artefactos: str | None = None,
) -> dict[str, object]:
    import mlflow

    corpus = json.loads(ruta_corpus.read_text(encoding="utf-8"))
    resultado = evaluar_corpus(corpus)
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    cliente = mlflow.MlflowClient()
    existente = cliente.get_experiment_by_name(experimento)
    experimento_id = (
        existente.experiment_id
        if existente
        else cliente.create_experiment(experimento, artifact_location=ubicacion_artefactos)
    )
    with mlflow.start_run(
        experiment_id=experimento_id, run_name="ag-02-ag-03-sintetico"
    ) as corrida:
        mlflow.log_params(
            {
                "dataset_sha256": resultado["dataset_sha256"],
                "proveedor": resultado["proveedor"],
                "version_configuracion": resultado["version_configuracion"],
                "casos": resultado["casos"],
            }
        )
        mlflow.log_metrics(
            {
                "ag_02_tasa_extraccion": float(str(resultado["ag_02_tasa_extraccion"])),
                "ag_03_tasa_evidencia": float(str(resultado["ag_03_tasa_evidencia"])),
                "flujo_tasa_combinada": float(str(resultado["flujo_tasa_combinada"])),
            }
        )
        mlflow.log_dict(resultado, "resultado_sintetico.json")
        resultado["corrida_id"] = corrida.info.run_id
    return resultado
