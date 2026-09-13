"""Extraccion local acotada de PDF/DOCX; OCR es un adaptador opcional."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from pypdf import PdfReader

from talentia.modules.documents.domain.modelos import (
    DocumentoLeido,
    LecturaDocumentoError,
    PaginaDocumento,
)

LectorOcr = Callable[[Path], tuple[PaginaDocumento, ...]]
MIME_PDF = "application/pdf"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_XML_DOCX_BYTES = 5 * 1024 * 1024
TEXTO_WORD = re.compile(rb"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.DOTALL)


def _paginas_pdf(ruta: Path) -> tuple[PaginaDocumento, ...]:
    try:
        lector = PdfReader(str(ruta))
        if lector.is_encrypted and lector.decrypt("") == 0:
            raise LecturaDocumentoError("pdf_protegido", "El PDF requiere una contrasena")
        return tuple(
            PaginaDocumento(numero, (pagina.extract_text() or "").strip())
            for numero, pagina in enumerate(lector.pages, start=1)
        )
    except LecturaDocumentoError:
        raise
    except Exception as error:
        raise LecturaDocumentoError("pdf_invalido", "No se pudo leer el PDF") from error


def _paginas_docx(ruta: Path) -> tuple[PaginaDocumento, ...]:
    try:
        with ZipFile(ruta) as archivo:
            entrada = archivo.getinfo("word/document.xml")
            if entrada.file_size > MAX_XML_DOCX_BYTES:
                raise LecturaDocumentoError(
                    "docx_invalido", "El contenido interno del DOCX excede el limite"
                )
            contenido = archivo.read("word/document.xml")
        textos = [
            html.unescape(fragmento.decode("utf-8")).strip()
            for fragmento in TEXTO_WORD.findall(contenido)
        ]
        return (PaginaDocumento(1, "\n".join(filter(None, textos)).strip()),)
    except LecturaDocumentoError:
        raise
    except (BadZipFile, KeyError, UnicodeDecodeError) as error:
        raise LecturaDocumentoError("docx_invalido", "No se pudo leer el DOCX") from error


def extraer_documento(
    ruta: str, tipo_mime: str, lector_ocr: LectorOcr | None = None
) -> DocumentoLeido:
    archivo = Path(ruta)
    if not archivo.is_file():
        raise LecturaDocumentoError("archivo_ausente", "El documento no esta disponible")
    if tipo_mime == MIME_PDF:
        paginas = _paginas_pdf(archivo)
    elif tipo_mime == MIME_DOCX:
        paginas = _paginas_docx(archivo)
    else:
        raise LecturaDocumentoError("tipo_no_soportado", "Tipo de documento no soportado")
    if any(pagina.texto.strip() for pagina in paginas):
        return DocumentoLeido(paginas, "texto")
    if tipo_mime == MIME_PDF and lector_ocr is not None:
        paginas_ocr = lector_ocr(archivo)
        if any(pagina.texto.strip() for pagina in paginas_ocr):
            return DocumentoLeido(paginas_ocr, "ocr")
    raise LecturaDocumentoError(
        "ocr_requerido",
        "El documento no contiene texto extraible y requiere revision u OCR",
    )
