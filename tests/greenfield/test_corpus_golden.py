import json
from pathlib import Path

from talentia.ai.guardrails.privacidad import PATRONES_PII


def test_corpus_tiene_veinte_cv_sinteticos_sin_pii() -> None:
    ruta = Path("tests/golden/corpus_cv_anonimizado.json")
    corpus = json.loads(ruta.read_text(encoding="utf-8"))
    assert len(corpus) >= 20
    assert len({item["id"] for item in corpus}) == len(corpus)
    for item in corpus:
        assert item["esperado"] in {"coincide", "revision"}
        assert not any(patron.search(item["texto"]) for _, patron in PATRONES_PII)
