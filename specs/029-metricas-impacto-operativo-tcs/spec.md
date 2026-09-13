# SPEC-029 — Métricas de impacto operativo TCS

- **Estado:** VERIFIED
- **Fuente:** Documento TCS: 25 h semanales, 10 h automatizables y 574 descartes tardíos.

## Problema y alcance

El piloto debe medir si reduce registro/cruce y mejora el filtro temprano, sin afirmar beneficios no demostrados.

## Requisitos

- **FR-029-001:** mostrar volumen por fuente, CV útiles/remitidos, duplicados prevenidos, evaluaciones tempranas y revisiones humanas.
- **FR-029-002:** definir `CV útil` mediante estados verificables y mostrar numerador, denominador y fórmula.
- **FR-029-003:** estimar horas evitadas con parámetros visibles/editables y separar línea base de resultados reales.
- **FR-029-004:** filtrar métricas por vacante, fuente y periodo.
- **NFR-029-001:** cálculos deterministas desde SQLite/auditoría, sin LLM.
- **NFR-029-002:** estados sin datos no muestran cero engañoso ni beneficios confirmados.
- **SEC-029-001:** métricas agregadas no exponen PII y requieren permisos de reportes.

## Fuera de alcance

Afirmar ROI, causalidad o reemplazo de reclutadores durante el piloto. Sin preguntas bloqueantes.
