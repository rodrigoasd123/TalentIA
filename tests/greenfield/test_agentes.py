from decimal import Decimal

from talentia.ai.agents.evaluador import evaluar, verificar_evidencia
from talentia.ai.agents.exclusiones import clasificar_exclusiones, generar_csv
from talentia.modules.evaluations.domain.modelos import Veredicto
from talentia.modules.recruitment.domain.modelos import RequisitoPerfil


def test_evaluador_verifica_original_y_no_inventa_ausencias() -> None:
    requisitos = (
        RequisitoPerfil("PY", "experiencia Python FastAPI", True, Decimal("70")),
        RequisitoPerfil("AWS", "experiencia AWS", False, Decimal("30")),
    )
    resultado = evaluar("doc-1", "Experiencia Python y FastAPI en APIs.", requisitos)
    assert resultado.resultados[0].veredicto is Veredicto.COINCIDE
    assert verificar_evidencia(
        "Experiencia Python y FastAPI en APIs.", resultado.resultados[0].evidencia[0]
    )
    assert resultado.resultados[1].veredicto is Veredicto.SIN_EVIDENCIA
    assert resultado.requiere_revision


def test_exclusion_protege_persona_en_cualquier_proceso() -> None:
    entradas = clasificar_exclusiones(
        [
            {
                "persona_id": "1",
                "documento": "123",
                "estado": "no_apto",
                "vigente": True,
                "motivo_generico": "No continua",
            },
            {
                "persona_id": "1",
                "documento": "123",
                "estado": "apto",
                "vigente": True,
                "motivo_generico": "No continua",
            },
            {
                "persona_id": "2",
                "documento": "456",
                "estado": "no_apto",
                "vigente": True,
                "motivo_generico": "No continua",
            },
        ]
    )
    assert [entrada.documento for entrada in entradas] == ["456"]
    csv, huella = generar_csv(entradas)
    assert b"456" in csv and b"123" not in csv
    assert len(huella) == 64
