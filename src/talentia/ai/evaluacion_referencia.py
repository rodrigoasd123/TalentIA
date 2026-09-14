"""Benchmark reproducible de AG-02 y AG-03 con corpus sintetico."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import cast

from talentia.ai.agents.evaluador import evaluar
from talentia.ai.agents.lector_cv import extraer_cv_paginas
from talentia.ai.guardrails.privacidad import sanitizar
from talentia.modules.recruitment.domain.modelos import RequisitoPerfil

ProveedorBenchmark = Callable[[str], dict[str, object]]


def evaluar_corpus(
    corpus: list[dict[str, object]], proveedor: ProveedorBenchmark | None = None
) -> dict[str, object]:
    if not corpus:
        raise ValueError("El benchmark requiere un corpus etiquetado no vacio")
    extracciones = 0
    evaluaciones_con_evidencia = 0
    combinadas = 0
    aciertos_extraccion = 0
    aciertos_evaluacion = 0
    falsos_avances = 0
    falsos_descartes = 0
    for caso in corpus:
        texto = str(caso["texto"])
        limpio = sanitizar(texto)
        if not isinstance(caso.get("etiquetas"), dict) or not caso.get("requisito"):
            raise ValueError("Cada caso requiere requisito y etiquetas independientes")
        etiquetas = cast(dict[str, object], caso["etiquetas"])
        if "extraccion_correcta" not in etiquetas or "veredicto" not in etiquetas:
            raise ValueError("Las etiquetas deben declarar extraccion_correcta y veredicto")
        if proveedor is not None:
            proveedor(limpio.texto)
        lectura = extraer_cv_paginas(str(caso["id"]), ((1, texto),))
        campos_extraidos = [campo for campo in lectura.campos if campo.valor is not None]
        extraccion_correcta = len(campos_extraidos) >= 2
        extracciones += int(extraccion_correcta)
        requisito = RequisitoPerfil("HAB", str(caso["requisito"]), True, Decimal("1"))
        evaluacion = evaluar(str(caso["id"]), texto, (requisito,))
        tiene_evidencia = bool(evaluacion.resultados[0].evidencia)
        veredicto_obtenido = evaluacion.resultados[0].veredicto.value
        veredicto_esperado = str(etiquetas["veredicto"])
        aciertos_extraccion += int(extraccion_correcta is bool(etiquetas["extraccion_correcta"]))
        aciertos_evaluacion += int(veredicto_obtenido == veredicto_esperado)
        falsos_avances += int(veredicto_obtenido == "coincide" and veredicto_esperado != "coincide")
        falsos_descartes += int(
            veredicto_obtenido != "coincide" and veredicto_esperado == "coincide"
        )
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
        "ag_02_acuerdo_etiquetas": aciertos_extraccion / total,
        "ag_03_acuerdo_etiquetas": aciertos_evaluacion / total,
        "tasa_falso_avance": falsos_avances / total,
        "tasa_falso_descarte": falsos_descartes / total,
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
                "ag_02_acuerdo_etiquetas": float(str(resultado["ag_02_acuerdo_etiquetas"])),
                "ag_03_acuerdo_etiquetas": float(str(resultado["ag_03_acuerdo_etiquetas"])),
                "tasa_falso_avance": float(str(resultado["tasa_falso_avance"])),
                "tasa_falso_descarte": float(str(resultado["tasa_falso_descarte"])),
            }
        )
        mlflow.log_dict(resultado, "resultado_sintetico.json")
        resultado["corrida_id"] = corrida.info.run_id
    return resultado
