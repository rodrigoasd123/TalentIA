# Aceptación — SPEC-009

## AC-009-001 — Total determinístico

Los filtros y el total se calculan en código usando pesos versionados; el modelo no puede entregar el total ni ejecutar acciones.

**Evidencia:** pruebas de dominio y grafo en `tests/ats/`.

## AC-009-002 — PII no cruza la frontera

El payload efectivo del adaptador externo no contiene las categorías personales definidas y conserva evidencia profesional suficiente.

**Evidencia:** `tests/ats/test_pii_leakage.py`.

## AC-009-003 — Documento hostil contenido

Una instrucción incrustada no altera el score, no produce correo o transición y fuerza revisión humana.

**Evidencia:** `tests/ats/test_prompt_injection.py`.
