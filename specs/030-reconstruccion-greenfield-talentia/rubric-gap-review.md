# Revision de alineacion con rubrica - SPEC-030

Fecha: 2026-09-13

Rama de trabajo: `codex/rubrica-greenfield-talentia`

Base revisada: `origin/codex/rubrica-greenfield-talentia` (`a18c67c`)

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
| Cinco agentes definidos | Cumple en backend | AG-01/04/05 deterministas; AG-02 y AG-03 separados y conectados al worker con evidencia | Completar UAT y benchmark gobernado |
| LangGraph y recuperacion | Cumple en backend | Diez nodos reales, estado seguro, checkpoint unico por nodo, correlacion, lease, timeout, reintento y reinicio probado sin duplicados | Telemetria persistente de fase 6 y aceptacion operativa |
| Evaluacion con evidencia | Cumple | AG-03 persiste valoracion por requisito y la web muestra evidencia minima navegable, fuente y fallback humano | UAT con usuarios del piloto |
| Revision humana | Cumple | Fallback fail-closed, evidencia navegable, formulario aceptar/corregir/rechazar, justificacion, correcciones, CSRF/RBAC/IDOR y decision/auditoria atomicas | UAT con usuarios del piloto |
| Interfaz Jinja2/HTMX | Parcial | Login, candidatos, evaluacion/HITL y polling de trabajos con estados pendiente/procesando/completado/revision/error | Formularios operativos de perfiles, postulaciones, CV y lotes |
| Importaciones y ex-TCS | Parcial | Staging, confirmacion, idempotencia y proyeccion web | Mapeo/correccion web completo y decisiones `BIZ-001/008` |
| Privacidad y prompt injection | Cumple en recorrido IA actual | API y worker bloquean instrucciones incrustadas antes de AG-02/03, retiran PII y no llaman proveedor remoto | Probar nuevamente al habilitar cualquier proveedor futuro |
| Auditoria | Cumple en flujos implementados | Cadena hash, evaluacion/revision atomicas y correlacion conservada en trabajo/checkpoints | Telemetria nodo a nodo de fase 6 y politica `BIZ-007` |
| Metricas y observabilidad | Parcial | Metricas basicas, scripts de laboratorio y MLflow historico | Persistir eventos de piloto, panel de baseline y benchmark greenfield |
| Calidad y regresion | Cumple fase 3 | 61 greenfield y 371 totales; web E2E, CSRF, RBAC, IDOR y decision concurrente; Ruff, formato, mypy y escaner aprobados | Resolver advertencias de dependencias antes de actualizar versiones |

## Orden de cierre recomendado

1. Completar formularios operativos de perfiles, postulaciones y CV.
2. Completar lotes, ex-TCS y exclusiones sin resolver decisiones BIZ bloqueadas.
3. Persistir metricas de piloto y ejecutar benchmark greenfield con MLflow.
4. Ejecutar aceptacion de usuarios.

## Decisiones que permanecen cerradas

`BIZ-001..010` siguen bloqueadas. Ningun cambio de esta rama asigna vigencia, umbrales de identidad,
retencion, criterios de CV util, alcance de identidad ni reglas BGC/Equifax. Los recorridos afectados
fallan cerrado o derivan a revision humana.
