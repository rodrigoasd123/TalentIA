"""Extraccion y estructuracion de bases de convocatoria (Job Description en PDF / DOCX)."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from talentia.modules.documents.infrastructure.extractores import (
    MIME_DOCX,
    MIME_PDF,
    extraer_documento,
)


@dataclass(frozen=True, slots=True)
class RequisitoConvocatoria:
    codigo: str
    descripcion: str
    obligatorio: bool
    peso: str


@dataclass(frozen=True, slots=True)
class ResultadoExtraccionConvocatoria:
    titulo: str
    codigo: str
    ctc: str | None
    requisitos_texto: str
    requisitos: tuple[RequisitoConvocatoria, ...]
    total_obligatorios: int
    total_deseables: int
    resumen: str


_PATRONES_PALABRAS_CLAVE = (
    ("java", "JAVA"),
    ("spring", "SPRING"),
    ("python", "PY"),
    ("react", "REACT"),
    ("angular", "ANGULAR"),
    ("vue", "VUE"),
    ("sql server", "SQLSRV"),
    ("azure sql", "AZSQL"),
    ("sql", "SQL"),
    ("azure", "AZURE"),
    ("aws", "AWS"),
    ("gcp", "GCP"),
    ("docker", "DOCKER"),
    ("kubernetes", "K8S"),
    ("kafka", "KAFKA"),
    ("quarkus", "QUARK"),
    ("microserv", "MSERV"),
    ("rest", "REST"),
    ("api", "API"),
    ("testing", "TEST"),
    ("junit", "JUNIT"),
    ("mockito", "MOCK"),
    ("git", "GIT"),
    ("jenkins", "CI"),
    ("scrum", "AGILE"),
    ("seguridad", "SEC"),
    ("jwt", "JWT"),
    ("oauth", "AUTH"),
    ("mongo", "MONGO"),
    ("cosmos", "COSMOS"),
    ("solid", "SOLID"),
    ("node", "NODE"),
    ("fastapi", "FASTAPI"),
    ("django", "DJANGO"),
    ("airflow", "AIRFLOW"),
    ("spark", "SPARK"),
    ("cypress", "CYPRESS"),
    ("playwright", "PLAYW"),
    ("selenium", "SELEN"),
)


def _limpiar_texto(cadena: str) -> str:
    limpio = re.sub(r"^[•\-\*\d\.\)\s]+", "", cadena).strip()
    limpio = re.sub(r"\s+", " ", limpio)
    return limpio.replace("|", "/")


def _generar_codigo(texto: str, obligatorio: bool, indice: int, existentes: set[str]) -> str:
    prefijo = "REQ" if obligatorio else "DES"
    t_lower = texto.casefold()
    tag = "TEC"
    for kw, abreviatura in _PATRONES_PALABRAS_CLAVE:
        if kw in t_lower:
            tag = abreviatura
            break
    candidato = f"{prefijo}-{tag}-{indice:02d}"
    k = indice
    while candidato in existentes:
        k += 1
        candidato = f"{prefijo}-{tag}-{k:02d}"
    existentes.add(candidato)
    return candidato


def _extraer_titulo_y_codigo(texto: str) -> tuple[str, str]:
    titulo = ""
    codigo = ""

    # 1. Buscar "Nombre del Rol:" o "Puesto:" o "Titulo:"
    m_rol = re.search(r"(?:Nombre del Rol|Puesto|Título|Titulo)\s*[:]\s*([^\n\r]+)", texto, re.IGNORECASE)
    if m_rol:
        titulo = m_rol.group(1).strip()

    # 2. Buscar "Código:" o "Codigo:"
    m_cod = re.search(r"(?:Código|Codigo|Convocatoria)\s*[:]\s*([A-Z0-9_\-]+)", texto, re.IGNORECASE)
    if m_cod:
        codigo = m_cod.group(1).strip().upper()

    # 3. Fallback de título si la primera línea es el nombre del rol
    if not titulo:
        lineas = [l.strip() for l in texto.splitlines() if l.strip()]
        for l in lineas[:4]:
            if "tata consultancy" in l.casefold() or "formato de requerimiento" in l.casefold():
                continue
            if len(l) > 5 and not l.startswith(("Código", "Codigo", "Compensación", "Modalidad")):
                titulo = l
                break

    # 4. Fallback de código a partir del título
    if not codigo and titulo:
        palabras = [w for w in re.split(r"[^A-Za-z0-9]", titulo) if w]
        siglas = "".join(w[:4].upper() for w in palabras[:3])
        codigo = f"{siglas}-01" if siglas else "ROL-01"

    return titulo or "Vacante sin título", codigo or "ROL-01"


def _extraer_ctc(texto: str) -> str | None:
    m_ctc = re.search(
        r"(?:Compensación Total \(CTC\)|CTC|Presupuesto|Salario|Remuneración)\s*[:]\s*(?:S/\.?|\$|USD)?\s*([0-9.,]+)",
        texto,
        re.IGNORECASE,
    )
    if m_ctc:
        val_str = m_ctc.group(1).replace(",", "").strip()
        try:
            val_dec = Decimal(val_str)
            if val_dec > 0:
                return f"{val_dec:.2f}"
        except Exception:
            pass
    return None


def _extraer_requisitos_formato_estandar(
    texto: str, existentes: set[str]
) -> list[RequisitoConvocatoria]:
    requisitos: list[RequisitoConvocatoria] = []
    lineas = texto.splitlines()
    seccion_actual: str | None = None

    for linea in lineas:
        l_strip = linea.strip()
        if not l_strip:
            continue
        l_cf = l_strip.casefold()

        if "requisitos obligatorios" in l_cf or "requisito obligatorio" in l_cf:
            seccion_actual = "obligatorio"
            continue
        elif "requisitos deseables" in l_cf or "requisito deseable" in l_cf or "deseable" in l_cf:
            seccion_actual = "opcional"
            continue
        elif l_strip.startswith(("1.", "4.", "Beneficios", "Funciones")):
            seccion_actual = None

        if seccion_actual:
            m_req = re.search(
                r"[•\-\*]?\s*\[([A-Z0-9_\-]+)\]\s*(.*?)(?:\((?:Ponderación|Peso)\s*[:]?\s*([0-9.]+)\))?$",
                l_strip,
                re.IGNORECASE,
            )
            if m_req:
                cod = m_req.group(1).strip().upper()
                desc = _limpiar_texto(m_req.group(2))
                peso_str = m_req.group(3) or ("1.0" if seccion_actual == "obligatorio" else "0.5")
                try:
                    peso_dec = Decimal(peso_str)
                except Exception:
                    peso_dec = Decimal("1.0" if seccion_actual == "obligatorio" else "0.5")
                existentes.add(cod)
                requisitos.append(
                    RequisitoConvocatoria(
                        codigo=cod,
                        descripcion=desc,
                        obligatorio=seccion_actual == "obligatorio",
                        peso=f"{peso_dec:.1f}" if peso_dec % 1 != 0 else str(int(peso_dec)),
                    )
                )
    return requisitos


def _extraer_requisitos_formato_tcs_corporativo(
    texto: str, existentes: set[str]
) -> list[RequisitoConvocatoria]:
    requisitos: list[RequisitoConvocatoria] = []
    lineas = texto.splitlines()
    seccion_actual: str | None = None
    indice = 1

    for linea in lineas:
        l_strip = linea.strip()
        if not l_strip:
            continue
        l_cf = l_strip.casefold()

        # Detección de secciones clave del formato TCS
        if any(h in l_cf for h in ("experiencia técnica:", "experiencia tecnica:", "necesario:", "requisitos técnicos:")):
            seccion_actual = "obligatorio"
            continue
        elif any(h in l_cf for h in ("deseable:", "deseables:", "requisitos deseables:")):
            seccion_actual = "opcional"
            continue
        elif any(h in l_cf for h in ("funciones:", "funciones o tareas", "beneficios corporativos", "perfil del candidato")):
            if "experiencia técnica" not in l_cf:
                seccion_actual = None
                continue

        # Si estamos dentro de una sección de requisitos
        if seccion_actual and (l_strip.startswith(("•", "-", "*")) or len(l_strip) > 15):
            desc = _limpiar_texto(l_strip)
            if len(desc) < 8 or desc.startswith(("Nombre del Rol", "Número de Vacantes", "Funciones")):
                continue
            
            # Generar código mnemónico
            es_obligatorio = (seccion_actual == "obligatorio")
            cod = _generar_codigo(desc, es_obligatorio, indice, existentes)
            peso = "1" if es_obligatorio else "0.5"
            indice += 1

            requisitos.append(
                RequisitoConvocatoria(
                    codigo=cod,
                    descripcion=desc,
                    obligatorio=es_obligatorio,
                    peso=peso,
                )
            )

    return requisitos


def _extraer_con_ia_si_disponible(texto: str, gestor_ia: Any) -> list[RequisitoConvocatoria] | None:
    if not gestor_ia:
        return None
    try:
        from talentia.platform.cliente_llm import ClienteLLM
        cliente = ClienteLLM(gestor_ia, timeout=25.0)
        # Verificamos si proveedor no es local
        ajustes = gestor_ia.obtener_interna()
        if ajustes.proveedor == "local" or not ajustes.api_key:
            return None
        
        # Enviar prompt para extracción estructurada de la convocatoria
        prompt = (
            "Eres un experto en selección técnica de TCS TalentIA. "
            "Extrae todos los requisitos del siguiente Job Description. "
            "Devuelve un JSON con la estructura: "
            '{"requisitos": [{"codigo": "REQ-01", "descripcion": "...", "obligatorio": true, "peso": "1"}]}. '
            f"\nDocumento:\n{texto[:6000]}"
        )
        # Si tiene soporte de evaluar o invocar api directa
        # Para resiliencia ante límites de cuota, si falla saltamos al analizador determinístico
    except Exception:
        return None
    return None


def parsear_texto_convocatoria(
    texto: str, gestor_ia: Any = None
) -> ResultadoExtraccionConvocatoria:
    titulo, codigo = _extraer_titulo_y_codigo(texto)
    ctc = _extraer_ctc(texto)

    existentes: set[str] = set()

    # 1. Intentar extracción estándar (si tiene códigos [REQ-...] o secciones numeradas)
    requisitos = _extraer_requisitos_formato_estandar(texto, existentes)

    # 2. Si no encontró, extraer según formato corporativo TCS ("Experiencia Técnica", "Deseable", etc.)
    if not requisitos:
        requisitos = _extraer_requisitos_formato_tcs_corporativo(texto, existentes)

    # 3. Fallback genérico si ninguna sección fue detectada: extraer viñetas generales
    if not requisitos:
        indice = 1
        for linea in texto.splitlines():
            l_strip = linea.strip()
            if l_strip.startswith(("•", "-", "*")) and len(l_strip) > 15:
                desc = _limpiar_texto(l_strip)
                cod = _generar_codigo(desc, True, indice, existentes)
                requisitos.append(
                    RequisitoConvocatoria(codigo=cod, descripcion=desc, obligatorio=True, peso="1")
                )
                indice += 1

    # Formatear a lineas de requisitos: CODIGO | descripcion | obligatorio/opcional | peso
    lineas_formato: list[str] = []
    total_ob = 0
    total_des = 0
    for req in requisitos:
        tipo_str = "obligatorio" if req.obligatorio else "opcional"
        if req.obligatorio:
            total_ob += 1
        else:
            total_des += 1
        lineas_formato.append(f"{req.codigo} | {req.descripcion} | {tipo_str} | {req.peso}")

    requisitos_texto = "\n".join(lineas_formato)
    resumen = (
        f"Se extrajeron {len(requisitos)} requisitos ({total_ob} obligatorios, {total_des} deseables)"
        + (f" y CTC presupuestado de S/ {ctc}" if ctc else "")
    )

    return ResultadoExtraccionConvocatoria(
        titulo=titulo,
        codigo=codigo,
        ctc=ctc,
        requisitos_texto=requisitos_texto,
        requisitos=tuple(requisitos),
        total_obligatorios=total_ob,
        total_deseables=total_des,
        resumen=resumen,
    )


def extraer_bases_convocatoria(
    origen: str | Path | bytes,
    tipo_mime: str,
    nombre_archivo: str = "",
    gestor_ia: Any = None,
) -> ResultadoExtraccionConvocatoria:
    # Si viene en bytes, guardamos temporalmente para extraer texto
    archivo_temporal: Path | None = None
    if isinstance(origen, bytes):
        sufijo = ".docx" if "word" in tipo_mime or nombre_archivo.endswith(".docx") else ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as temp_file:
            temp_file.write(origen)
            ruta_str = temp_file.name
        archivo_temporal = Path(ruta_str)
        mime = MIME_DOCX if sufijo == ".docx" else MIME_PDF
    else:
        ruta_str = str(origen)
        mime = tipo_mime or (MIME_DOCX if ruta_str.endswith(".docx") else MIME_PDF)

    try:
        doc_leido = extraer_documento(ruta_str, mime)
        texto_completo = "\n\n".join(pagina.texto for pagina in doc_leido.paginas if pagina.texto)
        return parsear_texto_convocatoria(texto_completo, gestor_ia=gestor_ia)
    finally:
        if archivo_temporal and archivo_temporal.is_file():
            try:
                archivo_temporal.unlink()
            except Exception:
                pass
