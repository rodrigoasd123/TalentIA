from datetime import date
from decimal import Decimal

from talentia.modules.candidates.domain.modelos import (
    Candidato,
    normalizar_documento,
    tokens_nombre,
    ultimos_nueve_telefono,
)


def test_derivados_no_se_persisten_y_se_calculan() -> None:
    candidato = Candidato(
        nombres="Ana",
        apellidos="Prueba",
        fecha_nacimiento=date(2000, 1, 1),
        expectativa_salarial=Decimal("120"),
        ctc_rol=Decimal("100"),
    )
    assert candidato.edad >= 26
    assert candidato.variacion_ctc_porcentaje == Decimal("20.00")


def test_identidad_se_normaliza_deterministicamente() -> None:
    assert normalizar_documento(" dni 12-34 ") == "DNI1234"
    assert ultimos_nueve_telefono("+51 987 654 321") == "987654321"
    assert tokens_nombre("Jose Alvarez") == tokens_nombre("Alvarez Jose")
