"""Extraccion local y determinista de datos generales presentes en un CV."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from talentia.ai.guardrails.privacidad import sanitizar


@dataclass(frozen=True, slots=True)
class PrecargaCandidato:
    campos: dict[str, object]
    procedencias: dict[str, str] = field(default_factory=dict)


ETIQUETAS_EXACTAS = {
    "nombres": "nombre_completo",
    "nombre": "nombre_completo",
    "apellidos": "apellidos",
    "documento": "documento",
    "fuente": "fuente",
    "perfil solicitado": "perfil_solicitado",
    "especialidad": "conocimiento_tecnico",
    "habilidades": "conocimiento_tecnico",
    "habilidades tecnicas": "conocimiento_tecnico",
    "skills": "conocimiento_tecnico",
}
PREFIJOS_ETIQUETAS = (
    ("dni", "documento"),
    ("correo", "correo"),
    ("telefono", "telefono"),
    ("celular", "telefono"),
    ("ubicaci", "ubicacion"),
    ("canal de atracci", "fuente"),
    ("postulaci", "perfil_solicitado"),
    ("convocatoria", "perfil_solicitado"),
    ("expectativa", "expectativa_salarial"),
    ("disponibilidad", "disponibilidad"),
)


def _clave(valor: str) -> str:
    sin_tildes = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", valor.casefold())
        if not unicodedata.combining(caracter)
    )
    return " ".join(re.findall(r"[a-z0-9]+", sin_tildes.replace("�", " ")))


def _limpiar(valor: str, maximo: int) -> str:
    return re.sub(r"\s+", " ", valor).strip(" -*`\t")[:maximo]


def _separar_nombre(nombre: str) -> tuple[str, str] | None:
    partes = [parte for parte in _limpiar(nombre, 280).split() if parte]
    if len(partes) < 2:
        return None
    corte = 2 if len(partes) >= 4 else 1
    return " ".join(partes[:corte])[:120], " ".join(partes[corte:])[:160]


def _monto(valor: str) -> Decimal | None:
    limpio = re.sub(r"[^0-9,.]", "", valor)
    if not limpio:
        return None
    if "," in limpio and "." in limpio:
        if limpio.rfind(".") > limpio.rfind(","):
            limpio = limpio.replace(",", "")
        else:
            limpio = limpio.replace(".", "").replace(",", ".")
    elif limpio.count(",") == 1 and len(limpio.rsplit(",", 1)[1]) <= 2:
        limpio = limpio.replace(",", ".")
    else:
        limpio = limpio.replace(",", "")
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None


def _segmentos(texto: str) -> list[tuple[str, str, str]]:
    encontrados: list[tuple[str, str, str]] = []
    for linea in texto.splitlines():
        for segmento in linea.split("|"):
            if ":" not in segmento:
                continue
            etiqueta, valor = segmento.split(":", 1)
            valor_limpio = _limpiar(valor, 500)
            if valor_limpio:
                encontrados.append((_clave(etiqueta), valor_limpio, _limpiar(linea, 600)))
    return encontrados


def _campo_para_clave(clave: str) -> str | None:
    exacto = ETIQUETAS_EXACTAS.get(clave)
    if exacto:
        return exacto
    return next((campo for prefijo, campo in PREFIJOS_ETIQUETAS if clave.startswith(prefijo)), None)


def _agregar_nombre_inicial(texto: str, valores: dict[str, tuple[str, str]]) -> None:
    if "nombre_completo" in valores:
        return
    primera = next((linea.strip() for linea in texto.splitlines() if linea.strip()), "")
    primera = re.sub(r"(?i)^\s*curriculum\s+vitae\s*[-:]?\s*", "", primera)
    if ":" not in primera and 1 < len(primera.split()) <= 8:
        valores["nombre_completo"] = (_limpiar(primera, 280), _limpiar(primera, 280))


def _materializar_campos(
    valores: dict[str, tuple[str, str]],
) -> tuple[dict[str, object], dict[str, str]]:
    campos: dict[str, object] = {}
    procedencias: dict[str, str] = {}
    nombre = valores.get("nombre_completo")
    apellidos_explicitos = valores.get("apellidos")
    if nombre and apellidos_explicitos:
        campos["nombres"] = _limpiar(nombre[0], 120)
        campos["apellidos"] = _limpiar(apellidos_explicitos[0], 160)
        procedencias.update({"nombres": nombre[1], "apellidos": apellidos_explicitos[1]})
    elif nombre and (separado := _separar_nombre(nombre[0])):
        campos["nombres"], campos["apellidos"] = separado
        procedencias.update({"nombres": nombre[1], "apellidos": nombre[1]})

    limites = {
        "tipo_documento": 20,
        "documento": 64,
        "correo": 255,
        "telefono": 40,
        "ubicacion": 160,
        "fuente": 80,
        "perfil_solicitado": 160,
        "conocimiento_tecnico": 2000,
        "disponibilidad": 100,
    }
    for campo, maximo in limites.items():
        if campo in valores:
            campos[campo] = _limpiar(valores[campo][0], maximo)
            procedencias[campo] = valores[campo][1]
    if "expectativa_salarial" in valores:
        monto = _monto(valores["expectativa_salarial"][0])
        if monto is not None:
            campos["expectativa_salarial"] = monto
            procedencias["expectativa_salarial"] = valores["expectativa_salarial"][1]
    return campos, procedencias


def extraer_precarga_candidato(texto: str) -> PrecargaCandidato:
    """Extrae solo valores explicitos; la llamada a sanitizar actua como guardrail local."""

    sanitizar(texto)
    segmentos = _segmentos(texto)
    valores: dict[str, tuple[str, str]] = {}

    for clave, valor, fuente in segmentos:
        campo = _campo_para_clave(clave)
        if campo is None:
            continue
        if campo == "correo":
            correo = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", valor, re.I)
            if not correo:
                continue
            valor = correo.group(0)
        valores.setdefault(campo, (valor, fuente))
        if campo == "documento":
            valores.setdefault("tipo_documento", ("DNI", fuente))

    _agregar_nombre_inicial(texto, valores)
    campos, procedencias = _materializar_campos(valores)
    return PrecargaCandidato(campos, procedencias)
