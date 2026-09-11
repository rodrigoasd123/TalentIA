"""Cifrado de secretos, configuración en caliente y estructura del grafo."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.agent import VeraAgent
from app.ai.graphs.evaluation_graph import build_evaluation_graph
from app.ai.graphs.runner import END, GraphDefinition, NativeGraphEngine
from app.ai.nodes.base import Node, NodeSpec
from app.ai.state import WorkflowState
from app.core.crypto import SecretCipher, mask_secret
from app.infrastructure.database.models import Base
from app.infrastructure.llm.mock_adapter import MockLLMAdapter
from app.infrastructure.settings_store import SETTINGS_CATALOG, SettingsStore


@pytest.fixture
def sesion() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ── Cifrado ──────────────────────────────────────────────────────────────────


def test_un_secreto_cifrado_se_recupera_intacto() -> None:
    cipher = SecretCipher("pruebas")
    original = "AIzaSyEJEMPLO1234567890abcdefghijklmn"
    cifrado = cipher.encrypt(original)

    assert cifrado != original
    assert cifrado.startswith("enc:v1:")
    assert cipher.decrypt(cifrado) == original


def test_dos_cifrados_del_mismo_valor_son_distintos() -> None:
    """Fernet incorpora un vector de inicialización aleatorio.

    Importa porque, de lo contrario, comparar dos filas cifradas revelaría que
    contienen el mismo secreto.
    """
    cipher = SecretCipher("pruebas")
    assert cipher.encrypt("mismo-valor") != cipher.encrypt("mismo-valor")


def test_claves_derivadas_por_proposito_no_son_intercambiables() -> None:
    """Comprometer el material de un propósito no compromete el resto."""
    from app.core.crypto import SecretDecryptionError

    cifrado = SecretCipher("proposito-a").encrypt("secreto")
    with pytest.raises(SecretDecryptionError):
        SecretCipher("proposito-b").decrypt(cifrado)


@pytest.mark.parametrize(
    "valor", ["AIzaSyEJEMPLO1234567890abcdefghij", "corto", "", "1234567890"]
)
def test_el_enmascarado_nunca_devuelve_el_valor_completo(valor: str) -> None:
    enmascarado = mask_secret(valor)
    if valor:
        assert enmascarado != valor
        assert "•" in enmascarado


# ── Configuración en caliente ────────────────────────────────────────────────


def test_un_secreto_se_guarda_cifrado_en_la_base_de_datos(sesion: Session) -> None:
    """La comprobación se hace sobre la fila, no sobre la API.

    Es la diferencia entre "la interfaz no lo muestra" y "no está ahí".
    """
    from app.infrastructure.database.models import RuntimeSettingModel

    store = SettingsStore(sesion)
    store.set("llm.api_key", "AIzaSyCLAVE1234567890abcdefghij")

    fila = sesion.get(RuntimeSettingModel, "llm.api_key")
    assert fila is not None
    assert "AIzaSyCLAVE" not in fila.value
    assert fila.value.startswith("enc:v1:")
    assert fila.is_secret


def test_la_vista_publica_enmascara_los_secretos(sesion: Session) -> None:
    store = SettingsStore(sesion)
    store.set("llm.api_key", "AIzaSyCLAVE1234567890abcdefghij")

    item = next(i for i in store.get_public_view() if i["key"] == "llm.api_key")
    assert "AIzaSyCLAVE1234567890abcdefghij" not in item["value"]
    assert item["is_set"] is True


def test_cada_proveedor_usa_su_propia_clave_cifrada(sesion: Session) -> None:
    store = SettingsStore(sesion)
    store.set("llm.genai_lab_api_key", "sk-clave-laboratorio")
    store.set("llm.gemini_api_key", "AIzaSyClaveGoogle")

    store.set("llm.model", "genailab-maas-gpt-4o")
    assert store.llm_config()["api_key"] == "sk-clave-laboratorio"
    assert store.llm_config()["provider"] == "genai_lab"

    store.set("llm.model", "gemini-3.6-flash")
    assert store.llm_config()["api_key"] == "AIzaSyClaveGoogle"
    assert store.llm_config()["provider"] == "gemini"


def test_una_clave_fuera_del_catalogo_se_rechaza(sesion: Session) -> None:
    """La tabla de configuración no puede convertirse en un cajón de sastre."""
    with pytest.raises(KeyError):
        SettingsStore(sesion).set("clave.inventada", "valor")


def test_los_flags_irreversibles_arrancan_desactivados(sesion: Session) -> None:
    flags = SettingsStore(sesion).feature_flags()
    assert flags["AI_AUTO_REJECTION"] is False
    assert flags["AUTO_EMAIL"] is False
    assert flags["DRY_RUN"] is True


def test_todo_el_catalogo_documenta_su_proposito() -> None:
    """Una opción sin explicación es una opción que nadie sabe si tocar."""
    for spec in SETTINGS_CATALOG:
        assert spec.label, f"{spec.key} no tiene etiqueta"
        assert spec.help_text, f"{spec.key} no explica para qué sirve"


# ── Estructura del grafo ─────────────────────────────────────────────────────


def test_el_grafo_se_valida_al_construirse() -> None:
    motor = build_evaluation_graph(MockLLMAdapter(), prefer_langgraph=False)
    assert isinstance(motor, NativeGraphEngine)
    motor.definition.validate()


def test_un_grafo_con_una_arista_rota_no_compila() -> None:
    definicion = GraphDefinition(name="roto")

    class Trivial(Node):
        spec = NodeSpec(name="trivial")

        def run(self, state: WorkflowState) -> WorkflowState:
            return state

    definicion.add_node(Trivial()).set_entry_point("trivial")
    definicion.add_edge("trivial", "nodo_inexistente")

    with pytest.raises(ValueError, match="inexistente"):
        NativeGraphEngine(definicion)


def test_un_nodo_inalcanzable_se_detecta() -> None:
    """Un nodo al que no llega ninguna arista es un error de cableado."""
    definicion = GraphDefinition(name="huerfano")

    class A(Node):
        spec = NodeSpec(name="a")

        def run(self, state: WorkflowState) -> WorkflowState:
            return state

    class B(Node):
        spec = NodeSpec(name="b")

        def run(self, state: WorkflowState) -> WorkflowState:
            return state

    definicion.add_node(A()).add_node(B()).set_entry_point("a")
    definicion.add_edge("a", END)

    with pytest.raises(ValueError, match="inalcanzable"):
        NativeGraphEngine(definicion)


def test_la_mayoria_de_los_nodos_son_deterministicos() -> None:
    """Propiedad estructural del diseño, no una casualidad de la implementación.

    Si alguien añade tres nodos con modelo, este test lo hace visible.
    """
    motor = build_evaluation_graph(MockLLMAdapter(), prefer_langgraph=False)
    nodos = motor.definition.nodes.values()
    deterministicos = sum(1 for n in nodos if n.spec.is_deterministic)
    assert deterministicos / len(nodos) >= 0.6, (
        f"Solo {deterministicos} de {len(nodos)} nodos son determinísticos"
    )


def test_todo_nodo_declara_lo_que_lee_y_escribe() -> None:
    motor = build_evaluation_graph(MockLLMAdapter(), prefer_langgraph=False)
    for nodo in motor.definition.nodes.values():
        assert nodo.spec.description, f"{nodo.spec.name} no tiene descripción"
        if nodo.spec.name != "audit":
            assert nodo.spec.reads or nodo.spec.writes, (
                f"{nodo.spec.name} no declara su contrato de estado"
            )


def test_los_filtros_duros_preceden_a_la_evaluacion_semantica() -> None:
    """Quien no cumple un requisito obligatorio no consume una llamada al modelo."""
    motor = build_evaluation_graph(MockLLMAdapter(), prefer_langgraph=False)
    condicional = motor.definition.conditional["hard_filter"][1]
    assert condicional["cumple"] == "candidate_scoring"
    assert condicional["no_cumple"] == "score_calculation"


def test_la_anonimizacion_precede_a_toda_llamada_al_modelo() -> None:
    """Propiedad estructural: no existe camino al modelo que evite la anonimización.

    No basta con comprobar el orden de un recorrido concreto: un grafo con
    ramificaciones puede tener un camino alternativo que se salte el nodo. La
    comprobación correcta es de alcanzabilidad: si se elimina la anonimización
    del grafo, **ningún** nodo con modelo debe seguir siendo alcanzable desde la
    entrada.
    """
    motor = build_evaluation_graph(MockLLMAdapter(), prefer_langgraph=False)
    definicion = motor.definition

    def sucesores(nombre: str) -> list[str]:
        if nombre in definicion.conditional:
            return list(definicion.conditional[nombre][1].values())
        destino = definicion.edges.get(nombre, END)
        return [destino]

    alcanzables: set[str] = set()
    pendientes = [definicion.entry_point]
    while pendientes:
        actual = pendientes.pop()
        # Se corta el paso por la anonimización: es lo que queremos demostrar
        # que resulta obligatorio.
        if actual in alcanzables or actual in {END, "pii_anonymization"}:
            continue
        alcanzables.add(actual)
        pendientes.extend(sucesores(actual))

    con_modelo = {
        nombre for nombre in alcanzables
        if not definicion.nodes[nombre].spec.is_deterministic
    }
    assert not con_modelo, (
        f"Estos nodos pueden invocar el modelo sin pasar por la anonimización: {con_modelo}"
    )


# ── Integración del agente ───────────────────────────────────────────────────


def test_el_agente_nunca_devuelve_acciones_ejecutadas(peticion) -> None:
    """El contrato central del sistema: VERA propone, no ejecuta."""
    resultado = VeraAgent(MockLLMAdapter(), prefer_langgraph=False).evaluate(peticion)

    for accion in resultado.proposed_actions:
        assert accion.action_type in {
            "request_human_review", "change_status", "prepare_email"
        }, f"Acción inesperada propuesta: {accion.action_type}"
    assert resultado.evaluation.workflow_run_id
    assert resultado.evaluation.trace_id


def test_toda_evaluacion_registra_su_procedencia(peticion) -> None:
    """Sin estos campos, una decisión pasada no puede explicarse."""
    evaluacion = VeraAgent(MockLLMAdapter(), prefer_langgraph=False).evaluate(
        peticion
    ).evaluation

    assert evaluacion.agent_version
    assert evaluacion.model_name
    assert evaluacion.prompt_versions
    assert "candidate_evaluation" in evaluacion.prompt_versions
    assert evaluacion.requirements_version >= 1


def test_el_fallo_del_proveedor_deriva_a_revision_y_no_rompe(peticion) -> None:
    """La caída de un servicio externo no puede traducirse en una decisión."""
    from app.domain.enums import ReviewReason

    llm_roto = MockLLMAdapter(fail_on="ResumeExtractionOutput")
    resultado = VeraAgent(llm_roto, prefer_langgraph=False).evaluate(peticion)

    assert resultado.requires_human_review
    assert ReviewReason.LLM_FAILURE in resultado.evaluation.review_reasons
    assert resultado.total_score == 0.0
