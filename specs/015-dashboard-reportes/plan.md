# Plan — SPEC-015

## Resumen técnico

Documentar retrospectivamente métricas y reportes operativos. El servicio analítico calcula sobre datos persistidos; FastAPI autoriza y entrega contratos, mientras Streamlit solo filtra y representa con Altair.

## Arquitectura y límites afectados

- `app/application/services/analytics_service.py` y repositorios.
- Rutas `/dashboard/*`, permisos y contratos API.
- `ats_frontend/pages/8_Dashboard.py`; pruebas ATS y smoke de SPEC-004.

## Flujo de datos

Actor autorizado + filtros → consulta persistida → agregación de resumen/funnel/SLA/fuentes/duración → respuesta API → estado vacío o visualización.

## Decisiones y alternativas

- Métricas en backend, no reglas duplicadas en Streamlit.
- Agregados de apoyo, no decisiones sobre personas.
- Solo exportaciones con contrato real; rediseño accesible queda en SPEC-017.

## Compatibilidad, transición y reversión

No cambia cálculos ni endpoints. Sin datos se devuelve una colección vacía. SPEC-017 puede sustituir presentación sin modificar contratos.

## Seguridad, privacidad y fallos

Permiso `APPLICATION_READ`, filtros validados y minimización. No se fabrican ceros o tendencias cuando falta información.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia |
|---|---|---|
| AC-015-001 | servicio/API | servicio analítico y `/dashboard/*` |
| AC-015-002 | RBAC | pruebas de endpoints protegidos |
| AC-015-003 | UI/manual | smoke; accesibilidad completa en SPEC-017 |

## Riesgos y mitigaciones

- Métricas divergentes: cálculo único en backend.
- Reidentificación: agregación y permisos.
- Estado vacío confuso: presentación explícita sin inventar datos.

## Aprobación

- [x] Plan retrospectivo aprobado por la persona responsable el 2026-09-10.
