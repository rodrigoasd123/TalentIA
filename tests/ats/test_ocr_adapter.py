from __future__ import annotations

import io

from pypdf import PdfWriter

from app.infrastructure.documents.text_extractor import TextExtractor


def test_pdf_sin_texto_activa_ocr_local(monkeypatch) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    stream = io.BytesIO()
    writer.write(stream)
    monkeypatch.setattr(
        "app.infrastructure.documents.postulaia_ocr.extract_pdf_with_ocr",
        lambda content, max_pages=40: (
            "[Página 1]\nAnalista de datos con experiencia en Python y SQL. " * 4,
            1,
        ),
    )
    result = TextExtractor().extract(content=stream.getvalue(), filename="cv.pdf")
    assert result.extraction_ok
    assert "[Página 1]" in result.text
    assert any("OCR local" in warning for warning in result.warnings)