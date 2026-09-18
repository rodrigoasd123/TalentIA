"""Nodos reales de AG-02/AG-03, sin estado documental crudo persistible."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from sqlalchemy import select

from talentia.ai.agents.evaluador import evaluar, verificar_evidencia
from talentia.ai.agents.lector_cv import extraer_cv_paginas
from talentia.ai.guardrails.privacidad import SanitizacionError, sanitizar
from talentia.ai.workflows.estado import EstadoEvaluacion
from talentia.modules.documents.domain.modelos import (
    DocumentoLeido,
    LecturaDocumentoError,
    ReferenciaFuente,
)
from talentia.modules.evaluations.domain.modelos import Veredicto
from talentia.modules.recruitment.domain.modelos import EstadoPostulacion, RequisitoPerfil
from talentia.platform.cliente_llm import ClienteLLM, ProveedorLLMError, RespuestaLLM
from talentia.shared.infrastructure.base_datos import FabricaSesiones
from talentia.shared.infrastructure.modelos_orm import (
    DocumentoCandidatoModelo,
    EvaluacionModelo,
    EvaluacionRequisitoModelo,
    ExtraccionDocumentoModelo,
    PostulacionModelo,
    RevisionHumanaModelo,
    SugerenciaCampoModelo,
    VersionPerfilPuestoModelo,
)
from talentia.shared.infrastructure.repositorio_sqlalchemy import RepositorioSqlalchemy


class ExtractorDocumento(Protocol):
    def __call__(self, ruta: str, tipo_mime: str) -> DocumentoLeido: ...


class WorkflowPermanenteError(RuntimeError):
    """Error permanente y sanitizado del workflow."""


def _entero(valor: object, predeterminado: int = -1) -> int:
    if isinstance(valor, int | str):
        return int(valor)
    return predeterminado


@dataclass(frozen=True, slots=True)
class ContextoNodosEvaluacion:
    fabrica: FabricaSesiones
    extractor: ExtractorDocumento
    cliente_llm: ClienteLLM | None = None

    def _documento(self, estado: EstadoEvaluacion) -> dict[str, str]:
        with self.fabrica.sesion() as sesion:
            modelo = sesion.get(DocumentoCandidatoModelo, estado["documento_id"])
            if modelo is None:
                raise WorkflowPermanenteError("documento_no_encontrado")
            return {
                "ruta": modelo.ruta_almacenamiento,
                "tipo_mime": modelo.tipo_mime,
                "cliente_id": modelo.cliente_id,
                "candidato_id": modelo.candidato_id,
            }

    def _leer(self, estado: EstadoEvaluacion) -> DocumentoLeido:
        documento = self._documento(estado)
        return self.extractor(documento["ruta"], documento["tipo_mime"])

    def validar_entradas(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        with self.fabrica.sesion() as sesion:
            postulacion = sesion.get(PostulacionModelo, estado["postulacion_id"])
            documento = sesion.get(DocumentoCandidatoModelo, estado["documento_id"])
            version = sesion.get(VersionPerfilPuestoModelo, estado["version_perfil_id"])
            valido = bool(
                postulacion
                and documento
                and version
                and postulacion.cliente_id == estado["cliente_id"]
                and documento.cliente_id == estado["cliente_id"]
                and postulacion.candidato_id == documento.candidato_id
                and postulacion.version_perfil_id == version.id
            )
        if not valido:
            raise WorkflowPermanenteError("contexto_evaluacion_invalido")
        return dict(estado)  # type: ignore[return-value]

    def cargar_documento(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        salida = dict(estado)
        try:
            leido = self._leer(estado)
            if not any(pagina.texto.strip() for pagina in leido.paginas):
                salida.update(error="ocr_requerido", revision_requerida=True)
        except LecturaDocumentoError as error:
            salida.update(error=error.codigo, revision_requerida=True)
        return cast(EstadoEvaluacion, salida)

    def sanitizar_pii(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        salida = dict(estado)
        if salida.get("revision_requerida"):
            return cast(EstadoEvaluacion, salida)
        try:
            texto = "\n".join(pagina.texto for pagina in self._leer(estado).paginas)
            sanitizar(texto)
        except SanitizacionError:
            salida.update(error="contenido_no_confiable", revision_requerida=True)
        except LecturaDocumentoError as error:
            salida.update(error=error.codigo, revision_requerida=True)
        return cast(EstadoEvaluacion, salida)

    def extraer_cv(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        salida = dict(estado)
        if salida.get("revision_requerida"):
            return cast(EstadoEvaluacion, salida)
        with self.fabrica.sesion() as sesion:
            existente = sesion.get(ExtraccionDocumentoModelo, estado["documento_id"])
            if existente is not None:
                salida["extraccion_id"] = existente.id
                salida["estado_extraccion"] = existente.estado
                if existente.error:
                    salida.update(error=existente.error, revision_requerida=True)
                return cast(EstadoEvaluacion, salida)
        try:
            leido = self._leer(estado)
            lectura = extraer_cv_paginas(
                estado["documento_id"],
                tuple((pagina.numero, pagina.texto) for pagina in leido.paginas),
            )
        except SanitizacionError:
            salida.update(error="contenido_no_confiable", revision_requerida=True)
            return cast(EstadoEvaluacion, salida)
        except LecturaDocumentoError as error:
            salida.update(error=error.codigo, revision_requerida=True)
            return cast(EstadoEvaluacion, salida)

        extraccion_id = estado["documento_id"]
        campos = {campo.campo: campo.valor for campo in lectura.campos}
        referencias = [asdict(campo.fuente) for campo in lectura.campos if campo.fuente]
        with self.fabrica.sesion() as sesion:
            if sesion.get(ExtraccionDocumentoModelo, extraccion_id) is None:
                sesion.add(
                    ExtraccionDocumentoModelo(
                        id=extraccion_id,
                        documento_id=estado["documento_id"],
                        estado="revision_manual" if lectura.requiere_revision else "completa",
                        texto_sanitizado=lectura.texto.texto,
                        campos=campos,
                        referencias=referencias,
                        error=None,
                    )
                )
                sesion.flush()
                for campo in lectura.campos:
                    if campo.valor is None or campo.fuente is None:
                        continue
                    sugerencia_id = hashlib.sha256(
                        f"{extraccion_id}:{campo.campo}".encode()
                    ).hexdigest()[:32]
                    if sesion.get(SugerenciaCampoModelo, sugerencia_id) is None:
                        sesion.add(
                            SugerenciaCampoModelo(
                                id=sugerencia_id,
                                extraccion_id=extraccion_id,
                                campo=campo.campo,
                                valor={"texto": campo.valor},
                                confianza=Decimal(str(campo.confianza)),
                                fuente=asdict(campo.fuente),
                                estado="pendiente",
                            )
                        )
        salida["extraccion_id"] = extraccion_id
        salida["estado_extraccion"] = "revision_manual" if lectura.requiere_revision else "completa"
        return cast(EstadoEvaluacion, salida)

    def validar_fuentes(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        salida = dict(estado)
        if salida.get("revision_requerida"):
            return cast(EstadoEvaluacion, salida)
        paginas = {pagina.numero: pagina.texto for pagina in self._leer(estado).paginas}
        with self.fabrica.sesion() as sesion:
            referencias = sesion.scalars(
                select(SugerenciaCampoModelo.fuente).where(
                    SugerenciaCampoModelo.extraccion_id == estado["extraccion_id"]
                )
            ).all()
        for referencia in referencias:
            pagina = referencia.get("pagina")
            original = paginas.get(_entero(pagina)) if pagina is not None else None
            inicio = _entero(referencia.get("inicio"))
            fin = _entero(referencia.get("fin"))
            fragmento = str(referencia.get("fragmento", ""))
            if original is None or original[inicio:fin] != fragmento:
                salida.update(error="fuente_extraccion_invalida", revision_requerida=True)
                break
        return cast(EstadoEvaluacion, salida)

    def relacionar_requisitos(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        salida = dict(estado)
        if salida.get("revision_requerida"):
            return cast(EstadoEvaluacion, salida)
        with self.fabrica.sesion() as sesion:
            version = sesion.get(VersionPerfilPuestoModelo, estado["version_perfil_id"])
            if version is None or not version.requisitos:
                salida.update(error="perfil_sin_requisitos", revision_requerida=True)
                return cast(EstadoEvaluacion, salida)
            try:
                requisitos = tuple(
                    RequisitoPerfil(
                        codigo=str(item["codigo"]),
                        descripcion=str(item["descripcion"]),
                        obligatorio=bool(item.get("obligatorio", True)),
                        peso=Decimal(str(item.get("peso", "1"))),
                    )
                    for item in version.requisitos
                )
            except (KeyError, InvalidOperation, TypeError, ValueError):
                salida.update(error="perfil_invalido", revision_requerida=True)
                return cast(EstadoEvaluacion, salida)
        texto_original = "\n".join(pagina.texto for pagina in self._leer(estado).paginas)
        if self.cliente_llm is not None:
            try:
                limpio = sanitizar(texto_original)
                sugerencia = self.cliente_llm.evaluar(
                    limpio.texto,
                    tuple((item.codigo, item.descripcion) for item in requisitos),
                )
                if sugerencia is not None:
                    return self._resultado_llm(salida, texto_original, requisitos, sugerencia)
            except SanitizacionError:
                salida.update(error="contenido_no_confiable", revision_requerida=True)
                return cast(EstadoEvaluacion, salida)
            except ProveedorLLMError:
                pass
        resultado = evaluar(estado["documento_id"], texto_original, requisitos)
        salida["resultados_requisitos"] = [
            {
                "codigo_requisito": item.codigo_requisito,
                "veredicto": item.veredicto.value,
                "puntaje": str(item.puntaje) if item.puntaje is not None else None,
                "evidencia": [asdict(fuente) for fuente in item.evidencia],
                "explicacion": item.explicacion,
            }
            for item in resultado.resultados
        ]
        salida["puntaje_documental"] = (
            str(resultado.puntaje) if resultado.puntaje is not None else None
        )
        salida["revision_requerida"] = resultado.requiere_revision
        return cast(EstadoEvaluacion, salida)

    @staticmethod
    def _resultado_llm(
        salida: dict[str, object],
        texto_original: str,
        requisitos: tuple[RequisitoPerfil, ...],
        respuesta: RespuestaLLM,
    ) -> EstadoEvaluacion:
        por_codigo = {
            str(item.get("codigo")): item for item in respuesta.requisitos if item.get("codigo")
        }
        resultados: list[dict[str, object]] = []
        revision = False
        documento_id = str(salida["documento_id"])
        for requisito in requisitos:
            item = por_codigo.get(requisito.codigo)
            veredicto = str(item.get("veredicto", "")) if item else ""
            cita = str(item.get("evidencia", "")).strip() if item else ""
            if veredicto not in {"coincide", "sin_evidencia", "revision_manual"}:
                veredicto = "revision_manual"
            evidencias: list[dict[str, object]] = []
            if cita:
                inicio = texto_original.casefold().find(cita.casefold())
                if inicio >= 0:
                    fin = inicio + len(cita)
                    evidencias.append(
                        asdict(
                            ReferenciaFuente(
                                documento_id,
                                None,
                                inicio,
                                fin,
                                texto_original[inicio:fin],
                            )
                        )
                    )
                else:
                    veredicto = "revision_manual"
            if veredicto == "coincide" and not evidencias:
                veredicto = "revision_manual"
            revision = revision or veredicto != "coincide"
            resultados.append(
                {
                    "codigo_requisito": requisito.codigo,
                    "veredicto": veredicto,
                    "puntaje": "100" if veredicto == "coincide" else None,
                    "evidencia": evidencias,
                    "explicacion": (
                        "Sugerencia del modelo con evidencia verificada en el CV original."
                        if evidencias
                        else "La sugerencia requiere verificacion humana por falta de evidencia."
                    ),
                }
            )
        coincidencias = sum(1 for item in resultados if item["veredicto"] == "coincide")
        salida["resultados_requisitos"] = resultados
        pesos_totales = sum((req.peso for req in requisitos), Decimal("0"))
        if pesos_totales > Decimal("0"):
            suma_ponderada = sum(
                (req.peso * Decimal("100") if item.get("veredicto") == "coincide" else Decimal("0"))
                for req, item in zip(requisitos, resultados)
            )
            salida["puntaje_documental"] = str(
                (suma_ponderada / pesos_totales).quantize(Decimal("0.01"))
            )
        else:
            salida["puntaje_documental"] = (
                str(round(coincidencias * 100 / len(resultados), 2)) if resultados else None
            )
        salida["revision_requerida"] = revision
        salida["proveedor_ia"] = respuesta.proveedor
        salida["modelo_ia"] = respuesta.modelo
        salida["prompt_tokens"] = respuesta.prompt_tokens
        salida["completion_tokens"] = respuesta.completion_tokens
        return cast(EstadoEvaluacion, salida)

    def verificar_evidencia_original(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        salida = dict(estado)
        resultados = list(estado.get("resultados_requisitos", []))
        if not resultados:
            salida["revision_requerida"] = True
            return cast(EstadoEvaluacion, salida)
        texto_original = "\n".join(pagina.texto for pagina in self._leer(estado).paginas)
        for resultado in resultados:
            evidencias = cast(list[dict[str, object]], resultado.get("evidencia", []))
            for datos in evidencias:
                fuente = ReferenciaFuente(
                    documento_id=str(datos["documento_id"]),
                    pagina=cast(int | None, datos.get("pagina")),
                    inicio=_entero(datos["inicio"]),
                    fin=_entero(datos["fin"]),
                    fragmento=str(datos["fragmento"]),
                )
                if fuente.documento_id != estado["documento_id"] or not verificar_evidencia(
                    texto_original, fuente
                ):
                    resultado["veredicto"] = Veredicto.REVISION_MANUAL.value
                    resultado["evidencia"] = []
                    resultado["puntaje"] = None
                    resultado["explicacion"] = "La evidencia no coincide con el CV original."
                    salida.update(error="evidencia_original_invalida", revision_requerida=True)
        salida["resultados_requisitos"] = resultados
        return cast(EstadoEvaluacion, salida)

    def veredicto_deterministico(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        salida = dict(estado)
        veredictos = {
            str(resultado.get("veredicto")) for resultado in estado.get("resultados_requisitos", [])
        }
        if not veredictos or veredictos != {Veredicto.COINCIDE.value}:
            salida["revision_requerida"] = True
        return cast(EstadoEvaluacion, salida)

    def persistir_evaluacion(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        salida = dict(estado)
        with self.fabrica.sesion() as sesion:
            evaluacion = sesion.get(EvaluacionModelo, estado["trabajo_id"])
            creada = evaluacion is None
            if evaluacion is None:
                puntaje_documental = estado.get("puntaje_documental")
                evaluacion = EvaluacionModelo(
                    id=estado["trabajo_id"],
                    cliente_id=estado["cliente_id"],
                    postulacion_id=estado["postulacion_id"],
                    documento_id=estado["documento_id"],
                    version_perfil_id=estado["version_perfil_id"],
                    puntaje_documental=(
                        Decimal(puntaje_documental) if puntaje_documental is not None else None
                    ),
                    requiere_revision=bool(estado.get("revision_requerida", True)),
                    modelo=str(estado.get("modelo_ia", "deterministico-local")),
                    version_prompt="evaluador-v2-gobernado",
                    simulada=False,
                )
                sesion.add(evaluacion)
                sesion.flush()
                for resultado in estado.get("resultados_requisitos", []):
                    requisito_id = hashlib.sha256(
                        f"{evaluacion.id}:{resultado['codigo_requisito']}".encode()
                    ).hexdigest()[:32]
                    sesion.add(
                        EvaluacionRequisitoModelo(
                            id=requisito_id,
                            evaluacion_id=evaluacion.id,
                            codigo_requisito=str(resultado["codigo_requisito"]),
                            veredicto=str(resultado["veredicto"]),
                            puntaje=(
                                Decimal(str(resultado["puntaje"]))
                                if resultado.get("puntaje") is not None
                                else None
                            ),
                            evidencia=cast(list[dict[str, object]], resultado.get("evidencia", [])),
                            explicacion=str(resultado.get("explicacion", "")),
                        )
                    )
                revision_id = hashlib.sha256(f"{evaluacion.id}:revision".encode()).hexdigest()[:32]
                sesion.add(
                    RevisionHumanaModelo(
                        id=revision_id,
                        evaluacion_id=evaluacion.id,
                        estado="pendiente",
                        comentario=None,
                    )
                )
                postulacion = sesion.get(PostulacionModelo, estado["postulacion_id"])
                if postulacion is not None and postulacion.estado not in {
                    EstadoPostulacion.NO_APTA.value,
                    EstadoPostulacion.RECHAZADA.value,
                    EstadoPostulacion.RETIRADA.value,
                    EstadoPostulacion.CONTRATADA.value,
                }:
                    postulacion.estado = EstadoPostulacion.REVISION_HUMANA.value
                    postulacion.version += 1
                RepositorioSqlalchemy(sesion).registrar_evento(
                    cliente_id=estado["cliente_id"],
                    actor_id=None,
                    accion="evaluacion.creada",
                    recurso_tipo="evaluacion",
                    recurso_id=evaluacion.id,
                    detalle={"requiere_revision": evaluacion.requiere_revision},
                    correlacion_id=estado["correlacion_id"],
                )
            salida["evaluacion_id"] = evaluacion.id
            if not creada:
                salida["revision_requerida"] = evaluacion.requiere_revision
        return cast(EstadoEvaluacion, salida)

    def revision_humana(self, estado: EstadoEvaluacion) -> EstadoEvaluacion:
        salida = dict(estado)
        salida["revision_requerida"] = True
        return cast(EstadoEvaluacion, salida)
