# SPEC-024 — Observabilidad MLflow y consumo de IA

- **Estado:** VERIFIED
- **Fecha:** 2026-09-12
- **Owner:** Product and engineering

## Problema

TalentIA necesita medir modelos sin registrar CV, prompts, respuestas, PII o secretos. La implementación reciente mezcla MLflow y una tabla OpenAI consultada directamente por Streamlit, y activa autologging que puede capturar contenido.

## Alcance

- Fuente única de telemetría accesible por FastAPI.
- Metadatos: proveedor, modelo, funcionalidad, tokens, latencia, costo estimado, estado y fecha.
- Persistencia local y panel autorizado.
- MLflow opcional, degradable y sin contenido.

## Fuera de alcance

- Observabilidad externa/productiva, LangSmith y almacenamiento de prompts/respuestas.

## Requisitos

- **FR-024-001:** cada llamada debe producir una métrica coherente por proveedor/modelo/función.
- **FR-024-002:** la UI debe consumir telemetría mediante FastAPI y respetar la base configurada.
- **FR-024-003:** MLflow debe persistir métricas entre reinicios y mostrar estado operativo.
- **NFR-024-001:** la caída de MLflow nunca bloquea el ATS ni una evaluación.
- **NFR-024-002:** los costos no conocidos deben mostrarse como no disponibles, no como cero real.
- **SEC-024-001:** trazas y runs no almacenan prompts, respuestas, CV, PII ni claves.
- **SEC-024-002:** la consulta requiere `settings:read`; configuración requiere `settings:write`.

## Riesgos

- Autologging captura contenido: se desactiva y se usa instrumentación explícita metadata-only.
- Doble conteo: una sola capa es responsable de persistir cada llamada.
- Sin preguntas bloqueantes.

## Referencias

Documento TCS, constitución y ADR-007.
