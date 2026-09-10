"""Suite de seguridad: ningún dato personal cruza hacia el proveedor de IA.

Este es el test más importante del repositorio. Sin él, la "capa de
anonimización" es una intención; con él, es una garantía verificada en cada
ejecución de la suite.

La prueba central no comprueba la salida del sanitizador: **intercepta el payload
real que se envía al modelo** y busca en él los datos del candidato. Es la
diferencia entre comprobar que la puerta se cierra y comprobar que nadie sale
por la ventana.
"""

from __future__ import annotations

import pytest

from app.ai.agent import EvaluationRequest, VeraAgent
from app.ai.guardrails.pii_sanitizer import PIISanitizer, assert_no_pii
from app.domain.enums import PIICategory
from app.infrastructure.llm.base import LLMResponse
from app.infrastructure.llm.mock_adapter import MockLLMAdapter

pytestmark = pytest.mark.security


CV_CON_PII = """
# Patricia Elena Cordero Maldonado

Nombre completo: Patricia Elena Cordero Maldonado
Fecha de nacimiento: 01/01/1900
Edad: 47 años
Género: Femenino
Estado civil: Casada, dos hijos
Nacionalidad: Peruana
DNI: 00000000
Dirección: Calle Ficticia 000, Distrito de Prueba
Teléfono: +00 000 000 000
Correo: patricia.cordero@example.test
LinkedIn: linkedin.com/in/patricia-cordero-ficticia
Foto: adjunta en la esquina superior derecha

Ingeniera con 16 años de experiencia en el área de datos.

Líder Técnica de Datos en Corporación Financiera (2018 - actualidad)
Trabajo con Python, SQL y Airflow sobre BigQuery.

Ingeniería de Sistemas, Universidad de Lima, graduación 2010.
Español nativo, inglés C1.
"""

#: Valores que jamás deben aparecer en lo que se envía al proveedor.
VALORES_PROHIBIDOS = [
    "Patricia Elena Cordero Maldonado",
    "Patricia",
    "Cordero",
    "patricia.cordero@example.test",
    "000 000 000",
    "00000000",
    "01/01/1900",
    "Calle Ficticia 000",
]


class SpyLLM(MockLLMAdapter):
    """Adaptador que registra literalmente todo lo que se le envía.

    Es la pieza clave del test: no confiamos en lo que el sanitizador dice haber
    hecho, sino en lo que efectivamente sale por el cable.
    """

    def __init__(self) -> None:
        super().__init__()
        self.payloads: list[str] = []

    def generate_json(self, **kwargs) -> LLMResponse:  # type: ignore[override]
        self.payloads.append(kwargs["system_instruction"] + "\n" + kwargs["user_content"])
        return super().generate_json(**kwargs)

    @property
    def todo_lo_enviado(self) -> str:
        return "\n".join(self.payloads)


def test_el_sanitizador_retira_las_categorias_conocidas() -> None:
    sanitizador = PIISanitizer(candidate_name="Patricia Elena Cordero Maldonado")
    resultado = sanitizador.anonymize(CV_CON_PII)

    encontradas = resultado.categories_found
    for categoria in (
        PIICategory.NAME, PIICategory.EMAIL, PIICategory.PHONE,
        PIICategory.NATIONAL_ID, PIICategory.BIRTH_DATE, PIICategory.AGE,
        PIICategory.GENDER, PIICategory.MARITAL_STATUS, PIICategory.NATIONALITY,
        PIICategory.URL_PROFILE,
    ):
        assert categoria in encontradas, f"No se retiró la categoría {categoria.value}"


def test_el_texto_anonimizado_no_contiene_datos_personales() -> None:
    sanitizador = PIISanitizer(candidate_name="Patricia Elena Cordero Maldonado")
    resultado = sanitizador.anonymize(CV_CON_PII)

    filtrados = assert_no_pii(resultado.anonymized_text, forbidden_values=VALORES_PROHIBIDOS)
    assert not filtrados, f"Datos personales que sobrevivieron: {filtrados}"


def test_la_informacion_profesional_se_conserva() -> None:
    """Anonimizar no puede vaciar el CV: la evaluación necesita el contenido.

    Un sanitizador demasiado agresivo destruiría la información que justifica la
    contratación, y el sistema dejaría de servir para nada.
    """
    sanitizador = PIISanitizer(candidate_name="Patricia Elena Cordero Maldonado")
    texto = sanitizador.anonymize(CV_CON_PII).anonymized_text.lower()

    for termino in ("python", "sql", "airflow", "bigquery", "16 años de experiencia"):
        assert termino in texto, f"Se perdió información profesional: {termino}"


@pytest.fixture
def requisitos_datos():
    """Criterios que este CV sí supera, para que el grafo llegue a evaluar.

    Es necesario porque los filtros duros cortocircuitan la evaluación semántica:
    con unos requisitos que el candidato no cumple, el nodo que envía el
    documento completo al modelo nunca llegaría a ejecutarse y el test no
    probaría lo que dice probar.
    """
    from app.domain.entities import JobRequirements
    from app.domain.enums import FilterOperator, ScoringDimension
    from app.domain.value_objects import HardFilter, ScoringWeights

    return JobRequirements(
        hard_filters=[
            HardFilter(
                field="years_experience", operator=FilterOperator.GTE, value=3,
                label="Mínimo 3 años", legal_basis="Autonomía en diseño de pipelines",
            ),
            HardFilter(
                field="skills", operator=FilterOperator.CONTAINS_ALL,
                value=["python", "sql"], label="Python y SQL",
                legal_basis="Herramientas centrales del puesto",
            ),
        ],
        weights=ScoringWeights(
            weights={ScoringDimension.TECHNICAL: 60.0, ScoringDimension.EXPERIENCE: 40.0}
        ),
        mandatory_skills=["python", "sql", "airflow"],
        min_years_experience=3.0,
    )


def test_ninguna_pii_llega_al_proveedor_en_el_pipeline_completo(requisitos_datos) -> None:
    """Prueba de frontera: se inspecciona el payload real enviado al modelo.

    Si este test falla, el sistema está enviando datos personales a un servicio
    externo y no debe desplegarse bajo ninguna circunstancia.
    """
    espia = SpyLLM()
    agente = VeraAgent(espia, prefer_langgraph=False)

    agente.evaluate(
        EvaluationRequest(
            application_id="pii", candidate_id="c", job_id="j", resume_id="r",
            resume_text=CV_CON_PII,
            candidate_name="Patricia Elena Cordero Maldonado",
            candidate_email="patricia.cordero@example.test",
            requirements=requisitos_datos,
            job_title="Ingeniera de Datos",
        )
    )

    assert espia.payloads, "No se registró ninguna llamada al proveedor"

    # Se comprueban TODAS las llamadas, no solo la de evaluación. La extracción
    # también sale hacia un servicio externo y debe estar igual de limpia.
    payload_evaluacion = next(
        (p for p in espia.payloads if "evaluador semántico" in p), ""
    )
    assert payload_evaluacion, (
        "El nodo de evaluación no llegó a ejecutarse; el test no probó la frontera"
    )
    payload_extraccion = next(
        (p for p in espia.payloads if "extractor de datos" in p), ""
    )
    assert payload_extraccion, "El nodo de extracción no llegó a ejecutarse"

    filtrados = assert_no_pii(espia.todo_lo_enviado, forbidden_values=VALORES_PROHIBIDOS)
    assert not filtrados, (
        f"FUGA DE DATOS PERSONALES hacia el proveedor de IA: {filtrados}"
    )


def test_el_mapa_de_identidades_permite_rehidratar() -> None:
    """El backend debe poder recuperar los valores reales para mostrarlos.

    La anonimización es reversible dentro del sistema y solo dentro del sistema:
    el mapa nunca acompaña al texto que sale.
    """
    sanitizador = PIISanitizer(candidate_name="Patricia Elena Cordero Maldonado")
    resultado = sanitizador.anonymize(CV_CON_PII)

    rehidratado = resultado.rehydrate(resultado.anonymized_text)
    assert "patricia.cordero@example.test" in rehidratado


def test_el_mapa_de_identidades_no_sale_en_el_resumen_de_estado(requisitos) -> None:
    """El resumen que va a logs y auditoría no puede arrastrar el mapa de PII."""
    agente = VeraAgent(MockLLMAdapter(), prefer_langgraph=False)
    resultado = agente.evaluate(
        EvaluationRequest(
            application_id="pii", candidate_id="c", job_id="j", resume_id="r",
            resume_text=CV_CON_PII,
            candidate_name="Patricia Elena Cordero Maldonado",
            candidate_email="patricia.cordero@example.test",
            requirements=requisitos, job_title="Ingeniera de Datos",
        )
    )

    serializado = str(resultado.state_summary)
    assert "pii_map" not in serializado
    filtrados = assert_no_pii(serializado, forbidden_values=VALORES_PROHIBIDOS)
    assert not filtrados, f"El resumen de estado filtró datos personales: {filtrados}"


def test_el_nodo_de_puntuacion_no_declara_acceso_al_mapa_de_pii() -> None:
    """Contrato de nodo: quien habla con el modelo no puede leer el mapa.

    La propiedad se verifica sobre la declaración del nodo, no sobre su
    ejecución: así se detecta la infracción aunque el camino que la explotaría
    todavía no exista.
    """
    from app.ai.nodes.deterministic import ScoreCalculationNode
    from app.ai.nodes.llm_nodes import BiasCheckNode, CandidateScoringNode, ResumeParserNode

    for nodo in (CandidateScoringNode, BiasCheckNode, ResumeParserNode, ScoreCalculationNode):
        assert "pii_map" not in nodo.spec.reads, (
            f"El nodo {nodo.spec.name} declara acceso a pii_map"
        )
        assert "candidate_email" not in nodo.spec.reads or nodo.spec.is_deterministic


def test_el_logger_redacta_datos_personales() -> None:
    """La redacción es del formatter, no del llamante."""
    from app.core.logging import redact

    redactado = redact(
        {
            "email": "patricia.cordero@example.test",
            "api_key": "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
            "mensaje": "contactar al +00 000 000 000",
            "pii_map": {"[NAME_1]": "Patricia"},
        }
    )

    serializado = str(redactado)
    assert "patricia.cordero@example.test" not in serializado
    assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in serializado
    assert "000 000 000" not in serializado
    assert redactado["pii_map"] == "[REDACTADO]"
