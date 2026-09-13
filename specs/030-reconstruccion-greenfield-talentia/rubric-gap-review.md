# Revision de alineacion con rubrica - SPEC-030

Fecha: 2026-09-13

Rama de trabajo: `codex/rubrica-greenfield-talentia`

Base revisada: `talentia/codex/implementacion-greenfield-talentia` (`979b575`)

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
| CV y almacenamiento privado | Parcial | Firma/tamano, hash, ruta privada, escritura atomica, PDF/DOCX local, PII sanitizada, sugerencias con fuente y fallback OCR manual | Conectar la extraccion al worker, elegir motor OCR si TCS lo requiere y definir `BIZ-007` |
| Cinco agentes definidos | Parcial | AG-01/04/05 deterministas; AG-02 ya extrae PDF/DOCX local con fuentes; AG-03 mantiene contrato | El worker no ejecuta todavia los nodos reales AG-02/03 |
| LangGraph y recuperacion | Parcial | Grafo de diez nodos, checkpoints, reintentos y recuperacion de reserva vencida | Ejecutar cada nodo real y probar reinicio entre nodos sin duplicados |
| Evaluacion con evidencia | Parcial | Extraccion y sugerencias idempotentes con pagina/fragmento; evaluaciones/requisitos persistibles | Integrar la extraccion aprobada y el evaluador en el procesador |
| Revision humana | Cumple en API | Fallback fail-closed, revision pendiente, resolucion unica, correcciones y auditoria atomica | Pantalla de decision y prueba E2E en navegador |
| Interfaz Jinja2/HTMX | Parcial | Login, navegacion, candidatos y proyecciones reales de todos los modulos | Formularios operativos y estados loading/error para los modulos restantes |
| Importaciones y ex-TCS | Parcial | Staging, confirmacion, idempotencia y proyeccion web | Mapeo/correccion web completo y decisiones `BIZ-001/008` |
| Privacidad y prompt injection | Parcial | API documental bloquea instrucciones incrustadas, retira PII y no dispone de proveedor remoto en AG-02 | Repetir garantia dentro del worker al conectarlo en fase 2 |
| Auditoria | Cumple en flujos implementados | Cadena hash y evento en operaciones criticas; revision en misma UoW | Correlacion completa dentro del worker y politica `BIZ-007` |
| Metricas y observabilidad | Parcial | Metricas basicas, scripts de laboratorio y MLflow historico | Persistir eventos de piloto, panel de baseline y benchmark greenfield |
| Calidad y regresion | Cumple actualmente | 44 greenfield y 354 totales; Ruff, formato, mypy y escaner aprobados | Resolver advertencias de dependencias antes de actualizar versiones |

## Orden de cierre recomendado

1. Conectar AG-02/AG-03 al worker con checkpoints por nodo y evidencia del CV original.
2. Crear pantalla de evaluacion y revision humana con aceptacion/correccion visible.
3. Completar formularios operativos de perfiles, postulaciones, CV y lotes.
4. Persistir metricas de piloto y ejecutar benchmark greenfield con MLflow.
5. Ejecutar E2E de navegador, prueba de reinicio y aceptacion de usuarios.

## Decisiones que permanecen cerradas

`BIZ-001..010` siguen bloqueadas. Ningun cambio de esta rama asigna vigencia, umbrales de identidad,
retencion, criterios de CV util, alcance de identidad ni reglas BGC/Equifax. Los recorridos afectados
fallan cerrado o derivan a revision humana.
