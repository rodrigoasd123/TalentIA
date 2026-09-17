# Plan técnico — SPEC-037

## Resumen técnico

La solución ampliará el monolito modular existente de TalentIA con una entidad de dominio
`Convocatoria` entre la versión publicada del perfil y las candidaturas. `Cliente` seguirá siendo
la cuenta operativa; `user_client_assignments` seguirá controlando el alcance de cuenta; una nueva
asignación convocatoria–reclutador expresará responsabilidad operativa sin conceder permisos
adicionales.

El flujo será determinístico y se implementará con Python, FastAPI, Jinja2/HTMX, SQLAlchemy,
Alembic y SQLite WAL. No participarán LLM, LangGraph, embeddings ni servicios externos en la
deduplicación, los cupos, las transiciones o las decisiones humanas.

La implementación se hará incrementalmente y sin reescribir los módulos existentes:

1. ampliar el dominio con convocatorias y una máquina de estados explícita;
2. migrar el esquema y asociar las postulaciones históricas a convocatorias compatibles;
3. incorporar persistencia y servicios transaccionales con alcance de cuenta;
4. exponer contratos API y páginas guiadas por la jerarquía aprobada;
5. verificar aislamiento, concurrencia, reversibilidad y operación sin IA.

## Arquitectura y límites afectados

### Decisión arquitectónica

Se mantiene un **monolito modular con capas de dominio, aplicación, infraestructura y web**. La
nueva funcionalidad pertenece al módulo `recruitment`; no se creará un microservicio por cuenta,
convocatoria o agente.

### Dominio

- `src/talentia/modules/recruitment/domain/modelos.py`
  - añadir `EstadoConvocatoria`, `Convocatoria`, `AsignacionConvocatoria` y las invariantes de cupos;
  - ampliar `EstadoPostulacion` con `contactada`, `apta`, `finalista`, `rechazada` y `backup`;
  - declarar la tabla de transiciones permitidas y las reglas que requieren motivo;
  - distinguir `no_apta` (no acredita criterios) de `rechazada` (decisión humana o del cliente);
  - impedir que aptitud, selección final o cierre sean inferidos por IA.
- `src/talentia/modules/access/domain/modelos.py`
  - añadir permisos específicos para administrar asignaciones bajo alcance, convocatorias y
    decisiones de selección, sin conceder `usuarios:administrar` al gestor de contratación.

### Aplicación

- `src/talentia/modules/recruitment/application/servicio_convocatorias.py` **(nuevo)**
  - concentrar casos de uso de alta, apertura, asignación de responsables, transición, selección,
    vista previa de cierre y cierre confirmado;
  - validar rol, alcance de cuenta, versión optimista, cupos y estado dentro de la transacción;
  - emitir eventos de auditoría con actor, cuenta, convocatoria, candidatura, estado anterior,
    estado nuevo y motivo.
- `src/talentia/shared/application/servicio_principal.py`
  - delegar los casos de uso nuevos al servicio focalizado;
  - conservar los puntos de entrada actuales durante la transición;
  - ampliar la asignación de cuentas para el gestor bajo alcance y mantener la invalidación de
    sesiones definida por SPEC-006.
- `src/talentia/shared/application/puertos.py`
  - añadir operaciones de repositorio para convocatorias, responsables, consultas paginadas,
    deduplicación acotada a cuenta y escrituras con versión esperada.

### Infraestructura y base de datos

- `src/talentia/shared/infrastructure/modelos_orm.py`
  - añadir `recruitment_campaigns` con cuenta, versión de perfil, código, cupos, fechas, estado,
    motivo de cierre, indicador de compatibilidad, marcas de tiempo y versión;
  - añadir `campaign_recruiter_assignments` con convocatoria, usuario, actor asignador y fecha;
  - añadir `campaign_id` a `applications` y unicidad por convocatoria y candidato;
  - mantener `version_perfil_id` en `applications` para preservar evaluación y downgrade.
- `src/talentia/shared/infrastructure/repositorio_sqlalchemy.py`
  - implementar consultas siempre acotadas a las cuentas autorizadas;
  - cargar contadores mediante agregaciones, no desde estados globales de candidato;
  - aplicar compare-and-swap con el campo de versión y devolver conflicto cuando esté obsoleto;
  - ejecutar cierre, conversión a backup y auditoría en una misma transacción.
- `migrations_greenfield/versions/0006_convocatorias_y_seleccion.py` **(nuevo)**
  - crear tablas, claves, restricciones e índices;
  - generar una convocatoria de compatibilidad por combinación cuenta–versión de perfil;
  - usar `vacantes_total = max(1, cantidad de postulaciones asociadas)` solo como capacidad de
    compatibilidad, marcarla explícitamente y conservar todos los campos de la postulación;
  - dejarla abierta si contiene candidaturas no terminales y cerrada si todas son terminales;
  - completar `campaign_id`, aplicar su obligatoriedad y verificar integridad;
  - permitir downgrade eliminando la relación nueva sin borrar la relación histórica con la
    versión del perfil.

Índices mínimos:

- `recruitment_campaigns(cliente_id, estado)`;
- `recruitment_campaigns(cliente_id, perfil_version_id)`;
- unicidad `recruitment_campaigns(cliente_id, codigo)`;
- `campaign_recruiter_assignments(campaign_id, user_id)` único;
- `applications(campaign_id, estado)`;
- `applications(cliente_id, candidato_id)` para antecedentes y deduplicación;
- unicidad `applications(campaign_id, candidato_id)`.

### API y presentación

- `src/talentia/web/schemas.py`
  - contratos para alta/edición de convocatoria, responsables, transición con versión esperada,
    selección de finalistas y cierre confirmado.
- `src/talentia/web/api.py`
  - exponer endpoints acotados por cuenta para convocatorias y responsables;
  - hacer que las nuevas candidaturas reciban `campaign_id` y que la versión del perfil se derive
    de la convocatoria;
  - exponer transición y cierre como comandos, no como actualización libre de columnas;
  - responder `404` sin confirmar existencia fuera de alcance y `409` ante versión obsoleta o cupo
    concurrente.
- `src/talentia/web/routes/paginas.py`
  - añadir rutas para el espacio de cuenta y el detalle de convocatoria;
  - conservar cuenta, perfil, convocatoria y filtros tras errores recuperables.
- `src/talentia/web/templates/cuentas.html` **(nuevo)**
  - selector y resumen de cuentas autorizadas.
- `src/talentia/web/templates/convocatorias.html` **(nuevo)**
  - perfiles y convocatorias de la cuenta seleccionada.
- `src/talentia/web/templates/detalle_convocatoria.html` **(nuevo)**
  - cupos, equipo, candidaturas por estado, alerta de contacto previo y acciones válidas.
- `src/talentia/web/templates/base.html`, `nueva_postulacion.html` y
  `src/talentia/web/static/css/aplicacion.css`
  - adaptar navegación, formularios y estados sin añadir una cadena de build frontend.

## Flujo de datos

```text
Usuario autenticado
    ↓ alcance efectivo de cuentas y permisos
Cuenta / Cliente
    ↓ perfil reusable
Versión publicada del perfil
    ↓ congela requisitos
Convocatoria (cupos, fechas, responsables, estado, versión)
    ↓ alta o carga de CV
Deduplicación determinística dentro de la cuenta
    ├─ coincidencia: advertencia con proceso, fecha y reclutador de la misma cuenta
    └─ sin coincidencia: expediente/candidatura nuevos
    ↓
Candidatura con estado y versión propios
    ↓ comandos de transición validados por rol, cuenta y estado
Apta → selección humana → Finalista → Entrevista → Oferta → Contratada
    ↓ cupos cubiertos
Vista previa de cierre → confirmación humana
    ├─ aptas no elegidas → Backup
    └─ convocatoria → Cerrada
```

Cada comando de escritura validará autorización y versión dentro de la misma unidad de trabajo,
persistirá el cambio y registrará auditoría antes de confirmar la transacción. Las páginas volverán
a consultar la base central; no mantendrán copias autoritativas en sesión, Excel o JavaScript.

## Decisiones y alternativas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Reutilizar `Cliente` como cuenta | Crear otra entidad `Cuenta` | Evita duplicar alcance, RBAC y datos existentes. |
| Entidad `Convocatoria` separada | Añadir cupos al perfil | El perfil es reusable; cupos, fechas y cierre pertenecen al proceso concreto. |
| Estado en candidatura | Estado global en candidato | Una persona puede tener resultados distintos por convocatoria. |
| Servicio de aplicación focalizado | Seguir ampliando únicamente `servicio_principal.py` | Reduce mezcla de responsabilidades sin una reescritura grande. |
| Máquina de estados Python | LLM/LangGraph para decidir estados | Las reglas son determinísticas, auditables y sensibles. |
| Auditoría existente | Tabla paralela de historial | `audit_events` ya satisface trazabilidad si se registran transiciones completas. |
| Bloqueo optimista | Bloqueos distribuidos/Redis | SQLite y la versión esperada son suficientes para el piloto local. |
| Jinja2/HTMX | React con Node en runtime | El flujo no necesita SPA y debe ejecutarse solo con Python. |

## Compatibilidad, transición y reversión

1. Crear las tablas nuevas y la columna inicialmente nullable.
2. Generar convocatorias de compatibilidad determinísticas antes de cambiar formularios.
3. Asociar cada postulación existente usando su `cliente_id` y `version_perfil_id`.
4. Comparar conteos, estados, documentos, evaluaciones, revisiones y marcas de tiempo antes y
   después del backfill.
5. Aplicar `NOT NULL`, claves foráneas, unicidad e índices solo después de validar el backfill.
6. Mantener `version_perfil_id` en la postulación durante esta versión para compatibilidad y
   downgrade.
7. Adaptar API/UI para que las altas nuevas usen convocatoria y rechazar combinaciones
   convocatoria–perfil–cuenta inconsistentes.
8. En rollback, retirar las restricciones y tablas nuevas; la postulación conserva su relación
   original, por lo que no se pierde el contexto previo.

Antes de desplegar se realizará un respaldo verificable de SQLite. La migración no borrará CV,
evaluación, revisión, auditoría ni candidatos y no tocará secretos o almacenamiento documental.

## Seguridad, privacidad y fallos

- Toda consulta recibirá el conjunto de cuentas autorizadas desde la sesión validada; no aceptará
  un `cliente_id` del formulario como prueba de autorización.
- Las respuestas fuera de alcance serán indistinguibles de un recurso inexistente y no incluirán
  conteos, nombres, coincidencias ni identificadores laterales.
- La deduplicación utilizará identificadores normalizados y hash/documento dentro de la cuenta;
  nunca anunciará coincidencias de otras cuentas.
- El gestor podrá asignar reclutadores solo a cuentas que administra. El administrador conserva el
  alcance global.
- Al retirar una asignación se incrementará la versión de sesión del usuario afectado y se auditará
  el antes/después.
- Motivo será obligatorio para `no_apta`, `rechazada`, `retirada`, reversiones y cierres/cancelaciones.
- Las exportaciones reutilizarán neutralización de fórmulas, minimizarán PII y filtrarán por cuenta.
- Una versión obsoleta devolverá `409 Conflict` con el estado vigente; la UI preservará el comentario
  del usuario para que pueda revisar y reintentar.
- Un cierre concurrente volverá a comprobar cupos y estados dentro de la transacción.
- Errores de proveedor de IA no impedirán ninguna operación de esta especificación.

## Estrategia de pruebas y evidencia

| Criterio | Tipo | Prueba o evidencia prevista |
|---|---|---|
| AC-037-001 | Web / visual | `tests/greenfield/test_convocatorias.py` **(nuevo)** y ampliación de `test_frontend_visual.py`: jerarquía, contexto y acciones válidas. |
| AC-037-002 | Dominio / repositorio / API | Dos convocatorias independientes sobre una versión publicada; restricciones de cuenta y código. |
| AC-037-003 | Integración | Coincidencia exacta por documento o correo dentro de cuenta, con advertencia y sin identidad duplicada. |
| AC-037-004 | Seguridad / API / web | Búsqueda, deduplicación y URL directa fuera de alcance devuelven respuesta opaca y evento IDOR. |
| AC-037-005 | Servicio / seguridad | Asignación por gestor bajo alcance, rechazo fuera de alcance, auditoría e invalidación de sesión. |
| AC-037-006 | Dominio / concurrencia / API | Aptitud separada de finalista, máximo de cupos y justificación humana auditable. |
| AC-037-007 | Transaccional / web | Vista previa, confirmación, cierre, backup automático y bloqueo de nuevas altas. |
| AC-037-008 | Concurrencia | Dos comandos con la misma versión: uno confirma y el otro recibe 409 conservando comentario. |
| AC-037-009 | Migración | Ampliación de `tests/greenfield/test_fase_7_operaciones.py`: upgrade/downgrade y comparación íntegra. |
| AC-037-010 | Integración sin red | Flujo completo sin claves ni clientes LLM, verificando cero invocaciones a proveedores. |

Verificación final prevista:

```powershell
.venv\Scripts\python.exe -m ruff check src/talentia migrations_greenfield tests/greenfield
.venv\Scripts\python.exe -m ruff format --check src/talentia migrations_greenfield tests/greenfield
.venv\Scripts\python.exe -m mypy src/talentia
.venv\Scripts\python.exe -m pytest tests/greenfield -q
```

La evidencia visual se verificará en escritorio y ancho móvil, además de navegación por teclado,
mensajes de bloqueo y persistencia de contexto tras un `409` recuperable.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Pérdida de contexto histórico durante backfill | Migración por fases, conteos e integridad antes de `NOT NULL`, conservar `version_perfil_id`. |
| Fuga entre cuentas por consulta incompleta | Filtros en repositorio y servicio, pruebas IDOR negativas y respuestas opacas. |
| Sobrepasar cupos por concurrencia | Versión esperada, revalidación transaccional y restricción lógica centralizada. |
| Permisos excesivos del hiring manager | Permisos granulares; nunca reutilizar `usuarios:administrar` para asignación acotada. |
| Contadores inconsistentes | Derivarlos de `applications` por convocatoria mediante agregaciones e índices. |
| Romper formularios y endpoints actuales | Adaptación incremental, contratos explícitos y pruebas de regresión de los flujos vigentes. |
| Inflar el servicio principal | Servicio de convocatorias focalizado y fachada de compatibilidad. |
| Confundir `backup` con estado global | Persistirlo exclusivamente en la candidatura y rotularlo por convocatoria. |

## Aprobación

- [x] Plan técnico aprobado para implementación.
- [x] Migración y estrategia de reversión aprobadas.
- [x] Mapeo de criterios de aceptación y evidencia aprobado.
