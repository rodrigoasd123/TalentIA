# Aceptación — SPEC-024

## AC-024-001 — Métricas persistentes

**Cubre:** FR-024-001, FR-024-003

```gherkin
Dada una llamada exitosa y una fallida
Cuando se consulta la observabilidad después de reiniciar
Entonces se conservan modelo, tokens, latencia y estado sin doble conteo
```

## AC-024-002 — Privacidad

**Cubre:** SEC-024-001

```gherkin
Dado un prompt con PII y un secreto marcador
Cuando se registra la llamada
Entonces ninguno aparece en parámetros, métricas, tags, trazas ni errores persistidos
```

## AC-024-003 — Frontera API

**Cubre:** FR-024-002, SEC-024-002

```gherkin
Dada la UI de consumo
Cuando carga métricas
Entonces usa FastAPI con autorización y no abre talentia.db directamente
```

## AC-024-004 — Degradación

**Cubre:** NFR-024-001, NFR-024-002

```gherkin
Dado MLflow indisponible y un modelo sin tarifa configurada
Cuando TalentIA procesa una llamada
Entonces el ATS continúa y el costo queda no disponible
```

**Evidencia (2026-09-12):** autologging de contenido retirado; UI sin acceso SQLite; `test_mlflow_observability.py` incluido en suite completa 310 passed.
