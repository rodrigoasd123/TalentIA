# Revision de alineacion con rubrica - SPEC-030

Fecha: 2026-09-13

Rama de trabajo: `codex/rubrica-greenfield-talentia`

Base revisada: `origin/codex/rubrica-greenfield-talentia` (`e5c924b`)

## Regla de lectura

- **Cumple:** existe implementacion y evidencia automatizada.
- **Parcial:** existe una parte util, pero falta un recorrido obligatorio o evidencia.
- **Bloqueado:** requiere una decision `BIZ` que el equipo no debe inventar.

## Matriz

| Area de rubrica | Estado | Evidencia actual | Brecha restante |
|---|---|---|---|
| Arquitectura modular Python | Cumple | `src/talentia`, puertos, UoW, API y web separados; pruebas de arquitectura | Ninguna P0 observada |
| Persistencia y migraciones | Cumple | Alembic greenfield, FK activas, SQLite WAL, rollback probado | Definir motor productivo fuera del piloto |
| Autenticacion, RBAC y alcance | Cumple | JWT/cookie firmada, CSRF web, roles, clientes y autoampliacion denegada | Aceptacion de usuarios del piloto |
| Base general de candidatos | Cumple | Preflight, 18 campos, busqueda, versionado optimista, traza | Definir `BIZ-004`, `BIZ-008..010` |
| CV y almacenamiento privado | Parcial | Firma/tamano, hash, ruta privada, escritura atomica, PDF/DOCX local, PII sanitizada, sugerencias con fuente y fallback OCR manual; worker conectado | Elegir motor OCR si TCS lo requiere y definir `BIZ-007` |
| Cinco agentes definidos | Cumple en backend | AG-01/04/05 deterministas; AG-02 y AG-03 separados, conectados al worker y comparados con corpus sintetico en MLflow | Completar UAT |
| LangGraph y recuperacion | Cumple en backend | Diez nodos reales, estado seguro, checkpoint y telemetria por nodo, correlacion, lease, timeout, reintento y reinicio sin duplicados | Aceptacion operativa |
| Evaluacion con evidencia | Cumple | AG-03 persiste valoracion por requisito y la web muestra evidencia minima navegable, fuente y fallback humano | UAT con usuarios del piloto |
| Revision humana | Cumple | Fallback fail-closed, evidencia navegable, formulario aceptar/corregir/rechazar, justificacion, correcciones, CSRF/RBAC/IDOR y decision/auditoria atomicas | UAT con usuarios del piloto |
| Interfaz Jinja2/HTMX | Cumple fase 5 | Login, candidatos, perfiles/versiones, postulaciones, CV/evaluacion, HITL, trabajos, lotes, ex-TCS y exclusiones con recorridos web | UAT de fase 8 |
| Importaciones y ex-TCS | Cumple fase 5 | Staging separado, mapeo/correccion, errores por fila, confirmacion/cancelacion, rollback, idempotencia, hash y revision humana | Decisiones `BIZ-001/008` permanecen bloqueadas |
| Exclusiones y descargas | Cumple fase 5 | AG-05 determinista, filtros y hash persistidos, CSV minimo, integridad, RBAC, IDOR y auditoria de crear/cambiar/consultar/descargar | Definir `BIZ-001` para producir vigencias reales |
| Privacidad y prompt injection | Cumple en recorrido IA actual | API y worker bloquean instrucciones incrustadas antes de AG-02/03, retiran PII y no llaman proveedor remoto | Probar nuevamente al habilitar cualquier proveedor futuro |
| Auditoria | Cumple en flujos implementados | Cadena hash, evaluacion/revision atomicas, lotes y descargas sensibles auditados; correlacion conservada | Telemetria nodo a nodo de fase 6 y politica `BIZ-007` |
| Metricas y observabilidad | Cumple fase 6 | Telemetria sanitizada correlacionada, tasas y percentiles reales, filtros protegidos y benchmark AG-02/03 reproducible en MLflow | `BIZ-006/007` y aceptacion del piloto |
| Calidad y regresion | Cumple fase 6 | 78 greenfield y 388 totales; Ruff, formato, mypy y escaner aprobados | Resolver advertencias al actualizar dependencias |

## Orden de cierre recomendado

1. Completar endurecimiento y aceptacion tecnica.
2. Ejecutar decisiones de negocio y UAT con aprobacion expresa.

## Decisiones que permanecen cerradas

`BIZ-001..010` siguen bloqueadas. Ningun cambio de esta rama asigna vigencia, umbrales de identidad,
retencion, criterios de CV util, alcance de identidad ni reglas BGC/Equifax. Los recorridos afectados
fallan cerrado o derivan a revision humana.
