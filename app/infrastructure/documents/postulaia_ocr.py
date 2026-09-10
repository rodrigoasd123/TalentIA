"""Adaptador del OCR local heredado de PostulaIA."""

from __future__ import annotations

from backend.pdf_reader import PdfReadError, read_pdf
from app.core.exceptions import ResumeParsingError


def extract_pdf_with_ocr(content: bytes, *, max_pages: int = 40) -> tuple[str, int]:
    """Reconoce texto visible y conserva marcadores de página verificables."""
    try:
        pages = read_pdf(content, mode="ocr")
    except PdfReadError as exc:
        raise ResumeParsingError(f"El OCR local no pudo procesar el PDF: {exc}") from exc
    selected = pages[:max_pages]
    text = "\n\n".join(
        f"[Página {page.page_number}]\n{page.text.strip()}"
        for page in selected
        if page.text.strip()
    )
    if not text:
        raise ResumeParsingError("El OCR local no reconoció texto útil en el PDF")
    return text, len(pages)


__all__ = ["extract_pdf_with_ocr"]