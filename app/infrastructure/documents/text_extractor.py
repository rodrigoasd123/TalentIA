"""Extracción de texto de documentos.

Primera línea de defensa frente a ficheros hostiles. Antes de leer nada se
comprueba la **firma binaria** del fichero, no su extensión: renombrar
``malware.exe`` a ``cv.pdf`` es el ataque más elemental que existe y hay que
descartarlo en el primer paso.

También se detecta cuándo la extracción produjo poco texto. Un PDF escaneado sin
capa de texto devuelve casi nada, y es importante distinguir "este CV está vacío"
de "no pudimos leer este CV": la primera conclusión perjudica al candidato por un
problema técnico nuestro.

Las dependencias de lectura son opcionales. Sin ellas, el sistema procesa texto
plano y Markdown, que es suficiente para el laboratorio.
"""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import (
    DocumentTooLarge,
    ResumeParsingError,
    UnsupportedDocumentType,
)
from app.core.logging import get_logger
from app.domain.enums import DocumentType

logger = get_logger(__name__)

#: Firmas binarias de los tipos admitidos.
_MAGIC_BYTES: tuple[tuple[bytes, DocumentType], ...] = (
    (b"%PDF-", DocumentType.PDF),
    (b"PK\x03\x04", DocumentType.DOCX),  # DOCX es un ZIP
)

#: Un fichero legítimo de CV rara vez baja de esto una vez extraído.
MIN_USEFUL_CHARS = 120

#: Límite de expansión al descomprimir un DOCX, contra bombas de descompresión.
MAX_DECOMPRESSION_RATIO = 120


@dataclass(slots=True)
class ExtractedText:
    """Resultado de la extracción, con las señales de alarma que se detectaron."""

    text: str
    char_count: int = 0
    page_count: int = 0
    document_type: DocumentType = DocumentType.TXT
    extraction_ok: bool = True
    warnings: list[str] = field(default_factory=list)
    hidden_text_found: bool = False
    content_hash: str = ""

    @property
    def looks_scanned(self) -> bool:
        """Poco texto repartido en varias páginas sugiere un documento escaneado."""
        return self.page_count > 0 and self.char_count < MIN_USEFUL_CHARS * self.page_count / 2


class TextExtractor:
    """Extrae texto de PDF, DOCX, TXT y Markdown."""

    def __init__(self, *, max_bytes: int = 10 * 1024 * 1024) -> None:
        self.max_bytes = max_bytes

    def extract(self, *, content: bytes, filename: str) -> ExtractedText:
        if len(content) > self.max_bytes:
            raise DocumentTooLarge(
                f"El fichero pesa {len(content) / 1_048_576:.1f} MB y el máximo es "
                f"{self.max_bytes / 1_048_576:.0f} MB"
            )
        if not content:
            raise ResumeParsingError("El fichero está vacío")

        document_type = self._detect_type(content, filename)
        content_hash = hashlib.sha256(content).hexdigest()

        extractors = {
            DocumentType.PDF: self._extract_pdf,
            DocumentType.DOCX: self._extract_docx,
            DocumentType.TXT: self._extract_plain,
            DocumentType.MARKDOWN: self._extract_plain,
        }
        result = extractors[document_type](content)
        result.document_type = document_type
        result.content_hash = content_hash
        result.text = self._clean(result.text)
        result.char_count = len(result.text)

        if result.char_count < MIN_USEFUL_CHARS:
            result.extraction_ok = False
            result.warnings.append(
                f"Solo se extrajeron {result.char_count} caracteres. "
                "Puede tratarse de un documento escaneado sin capa de texto."
            )
        if result.looks_scanned:
            result.warnings.append(
                "La densidad de texto por página es muy baja: probable documento escaneado."
            )

        logger.info(
            "Documento procesado",
            filename=Path(filename).name,
            type=document_type.value,
            chars=result.char_count,
            pages=result.page_count,
            ok=result.extraction_ok,
            hidden_text=result.hidden_text_found,
        )
        return result

    def extract_file(self, path: str | Path) -> ExtractedText:
        file_path = Path(path)
        return self.extract(content=file_path.read_bytes(), filename=file_path.name)

    # ── Detección de tipo ────────────────────────────────────────────────────

    @staticmethod
    def _detect_type(content: bytes, filename: str) -> DocumentType:
        """Determina el tipo por firma binaria; la extensión solo desempata.

        Un fichero cuya extensión dice PDF pero cuyos bytes dicen otra cosa se
        rechaza: es señal de manipulación, no de despiste.
        """
        header = content[:8]
        for magic, doc_type in _MAGIC_BYTES:
            if header.startswith(magic):
                return doc_type

        suffix = Path(filename).suffix.lower()
        if suffix in {".pdf", ".docx"}:
            raise UnsupportedDocumentType(
                f"La extensión dice «{suffix}» pero el contenido del fichero no lo es. "
                "El documento se rechaza por seguridad."
            )
        if suffix in {".md", ".markdown"}:
            return DocumentType.MARKDOWN
        if suffix in {".txt", ".text", ""}:
            return DocumentType.TXT

        raise UnsupportedDocumentType(
            f"Tipo de documento no admitido: «{suffix}». Se aceptan PDF, DOCX, TXT y Markdown."
        )

    # ── Extractores ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_pdf(content: bytes) -> ExtractedText:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ResumeParsingError(
                "Falta la dependencia para leer PDF. Instálala con: "
                "pip install 'talentia[documents]'"
            ) from exc

        warnings: list[str] = []
        try:
            reader = PdfReader(io.BytesIO(content))
        except Exception as exc:  # noqa: BLE001 — pypdf lanza tipos variados
            raise ResumeParsingError(f"El PDF está dañado o cifrado: {type(exc).__name__}") from exc

        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception as exc:  # noqa: BLE001
                raise ResumeParsingError("El PDF está protegido con contraseña") from exc

        pages: list[str] = []
        for index, page in enumerate(reader.pages):
            if index >= 40:
                warnings.append("Se procesaron solo las primeras 40 páginas")
                break
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:  # noqa: BLE001 — una página rota no anula el resto
                warnings.append(f"No se pudo leer la página {index + 1}")
                logger.warning("Página ilegible", page=index + 1, error=type(exc).__name__)

        text = "\n\n".join(pages)
        if len(text.strip()) < MIN_USEFUL_CHARS:
            from app.infrastructure.documents.postulaia_ocr import extract_pdf_with_ocr

            try:
                text, ocr_page_count = extract_pdf_with_ocr(content, max_pages=40)
                warnings.append("Se aplicó OCR local porque la extracción normal fue insuficiente")
                return ExtractedText(
                    text=text,
                    page_count=ocr_page_count,
                    warnings=warnings,
                    hidden_text_found=False,
                )
            except ResumeParsingError as exc:
                warnings.append(str(exc))
        return ExtractedText(
            text=text,
            page_count=len(reader.pages),
            warnings=warnings,
            # El texto invisible se detecta aquí porque es un truco específico de
            # los PDF: quien lo usa quiere que lo lea la máquina y no la persona.
            hidden_text_found=_has_invisible_characters(text),
        )

    @staticmethod
    def _extract_docx(content: bytes) -> ExtractedText:
        try:
            import docx  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ResumeParsingError(
                "Falta la dependencia para leer DOCX. Instálala con: "
                "pip install 'talentia[documents]'"
            ) from exc

        _check_zip_bomb(content)

        try:
            document = docx.Document(io.BytesIO(content))
        except Exception as exc:  # noqa: BLE001
            raise ResumeParsingError(f"El DOCX está dañado: {type(exc).__name__}") from exc

        parts = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))

        text = "\n".join(parts)
        return ExtractedText(text=text, page_count=0, hidden_text_found=_has_invisible_characters(text))

    @staticmethod
    def _extract_plain(content: bytes) -> ExtractedText:
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = content.decode("utf-8", errors="replace")
        return ExtractedText(text=text, hidden_text_found=_has_invisible_characters(text))

    # ── Limpieza ─────────────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        """Normaliza sin destruir información.

        La normalización agresiva se hace después, en el sanitizador. Aquí solo
        se arreglan artefactos de extracción: saltos sobrantes y espacios
        raros de los PDF.
        """
        normalized = unicodedata.normalize("NFKC", text)
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t ]+", " ", normalized)
        normalized = re.sub(r"\n{4,}", "\n\n\n", normalized)
        return normalized.strip()


def _has_invisible_characters(text: str) -> bool:
    """Detecta caracteres invisibles usados para esconder contenido."""
    suspicious = ("​", "‌", "‍", "⁠", "﻿", "‮", "‭")
    return sum(text.count(c) for c in suspicious) > 3


def _check_zip_bomb(content: bytes) -> None:
    """Comprueba que el DOCX no se expande de forma desproporcionada."""
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            uncompressed = sum(info.file_size for info in archive.infolist())
    except zipfile.BadZipFile as exc:
        raise ResumeParsingError("El fichero DOCX no es un ZIP válido") from exc

    if uncompressed > len(content) * MAX_DECOMPRESSION_RATIO:
        raise DocumentTooLarge(
            f"El documento se expande {uncompressed / max(1, len(content)):.0f} veces "
            "al descomprimirse. Se rechaza por seguridad."
        )


__all__ = ["MIN_USEFUL_CHARS", "ExtractedText", "TextExtractor"]
