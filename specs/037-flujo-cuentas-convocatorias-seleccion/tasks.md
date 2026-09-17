# Tareas — SPEC-037

## T037-001 — Modelar convocatorias, permisos y máquina de estados

**Cubre:** FR-037-002, FR-037-003, FR-037-005, FR-037-009, FR-037-010,
NFR-037-001, SEC-037-005; AC-037-002, AC-037-006, AC-037-010.

**Archivos:**

- `src/talentia/modules/recruitment/domain/modelos.py`
- `src/talentia/modules/access/domain/modelos.py`
- `tests/greenfield/test_dominio.py`
- `tests/greenfield/test_convocatorias.py` **(nuevo)**

**Trabajo:**

1. Crear los tipos de dominio de convocatoria, asignación y sus estados.
2. Ampliar los estados de candidatura y declarar transiciones, roles y motivos obligatorios.
3. Implementar invariantes de perfil publicado, fechas, cupos y separación apta/finalista.
4. Añadir permisos granulares sin elevar al gestor a administrador global.
5. Probar reglas puras sin base de datos, red ni proveedor de IA.

**Verificación:** pruebas unitarias de estados válidos/inválidos, cupos, motivos, roles y ausencia de
dependencias LLM.

**Dependencias:** ninguna.

## T037-002 — Incorporar esquema, índices y migración reversible

**Cubre:** FR-037-003, FR-037-004, FR-037-014, NFR-037-002, NFR-037-005;
AC-037-002, AC-037-009.

**Archivos:**

- `src/talentia/shared/infrastructure/modelos_orm.py`
- `migrations_greenfield/versions/0006_convocatorias_y_seleccion.py` **(nuevo)**
- `tests/greenfield/test_fase_7_operaciones.py`
- `tests/greenfield/test_convocatorias.py` **(nuevo)**

**Trabajo:**

1. Crear `recruitment_campaigns` y `campaign_recruiter_assignments` con restricciones e índices.
2. Añadir `campaign_id` y unicidad convocatoria–candidato a `applications`.
3. Crear convocatorias de compatibilidad y ejecutar el backfill sin alterar evidencia histórica.
4. Verificar conteos y relaciones antes de aplicar obligatoriedad.
5. Implementar downgrade conservando la relación original con la versión del perfil.

**Verificación:** base temporal con postulaciones, documentos, evaluaciones y revisiones; ejecutar
upgrade/downgrade y comparar identificadores, estados, fechas y conteos.

**Dependencias:** T037-001.

## T037-003 — Extender puertos y repositorio con alcance y concurrencia

**Cubre:** FR-037-006, FR-037-007, FR-037-012, FR-037-013, NFR-037-002,
NFR-037-003, SEC-037-001, SEC-037-002; AC-037-003, AC-037-004, AC-037-008.

**Archivos:**

- `src/talentia/shared/application/puertos.py`
- `src/talentia/shared/infrastructure/repositorio_sqlalchemy.py`
- `tests/greenfield/test_convocatorias.py` **(nuevo)**
- `tests/greenfield/test_seguridad.py`

**Trabajo:**

1. Definir operaciones de alta, consulta paginada, responsables, conteos y cierre.
2. Aplicar alcance de cuenta dentro de todas las consultas de convocatoria y candidatura.
3. Reutilizar deduplicación determinística filtrada por cuenta y devolver antecedentes permitidos.
4. Añadir compare-and-swap por versión para candidatura y convocatoria.
5. Calcular cupos y cantidades desde candidaturas sin doble conteo.

**Verificación:** pruebas SQLAlchemy de alcance, índices consultables, agregaciones, no filtración y
conflicto al escribir dos veces la misma versión.

**Dependencias:** T037-002.

## T037-004 — Gobernar asignaciones de cuenta y convocatoria

**Cubre:** FR-037-008, SEC-037-003, SEC-037-004; AC-037-005.

**Archivos:**

- `src/talentia/modules/recruitment/application/servicio_convocatorias.py` **(nuevo)**
- `src/talentia/shared/application/servicio_principal.py`
- `src/talentia/web/schemas.py`
- `src/talentia/web/api.py`
- `tests/greenfield/test_seguridad.py`
- `tests/greenfield/test_api.py`

**Trabajo:**

1. Permitir que un gestor asigne o retire reclutadores solo en cuentas bajo su alcance.
2. Designar responsables de convocatoria únicamente entre usuarios activos con acceso a la cuenta.
3. Impedir que una responsabilidad de convocatoria amplíe el alcance de cuenta.
4. Invalidar la sesión efectiva al cambiar asignaciones de cuenta.
5. Auditar actor, cuenta, usuario, valor anterior y valor nuevo.

**Verificación:** casos administrador, gestor autorizado/no autorizado y reclutador; comprobación de
versión de sesión y eventos de auditoría.

**Dependencias:** T037-003.

## T037-005 — Implementar casos de uso y contratos de convocatoria

**Cubre:** FR-037-002, FR-037-003, FR-037-004, FR-037-012, FR-037-013;
AC-037-001, AC-037-002.

**Archivos:**

- `src/talentia/modules/recruitment/application/servicio_convocatorias.py` **(nuevo)**
- `src/talentia/shared/application/servicio_principal.py`
- `src/talentia/web/schemas.py`
- `src/talentia/web/api.py`
- `tests/greenfield/test_api.py`
- `tests/greenfield/test_convocatorias.py` **(nuevo)**

**Trabajo:**

1. Implementar crear, abrir, consultar y listar convocatorias por cuenta/perfil.
2. Exigir versión publicada y derivar de ella la versión de perfil de cada candidatura.
3. Impedir altas duplicadas por convocatoria y altas sobre convocatorias cerradas.
4. Exponer contratos explícitos y respuestas paginadas con cupos y cantidades.
5. Registrar auditoría transaccional en cada comando.

**Verificación:** pruebas de dominio, servicio y API para dos convocatorias del mismo perfil,
cuentas incompatibles, códigos duplicados y estados de convocatoria.

**Dependencias:** T037-003, T037-004.

## T037-006 — Implementar selección humana, cupos, backup y cierre

**Cubre:** FR-037-009, FR-037-010, FR-037-011, FR-037-013, NFR-037-003,
SEC-037-005; AC-037-006, AC-037-007, AC-037-008.

**Archivos:**

- `src/talentia/modules/recruitment/application/servicio_convocatorias.py` **(nuevo)**
- `src/talentia/shared/infrastructure/repositorio_sqlalchemy.py`
- `src/talentia/web/schemas.py`
- `src/talentia/web/api.py`
- `tests/greenfield/test_convocatorias.py` **(nuevo)**
- `tests/greenfield/test_api.py`

**Trabajo:**

1. Implementar comandos de transición con estado y versión esperados.
2. Separar decisión de aptitud de selección de finalistas.
3. Aplicar el máximo de finalistas activos y revalidarlo dentro de la transacción.
4. Generar vista previa de cierre sin escritura.
5. Confirmar cierre, verificar cupos cubiertos y pasar aptas no elegidas a `backup` atómicamente.
6. Devolver conflicto recuperable con estado actual cuando la versión sea obsoleta.

**Verificación:** pruebas transaccionales y concurrentes, auditoría completa, motivo obligatorio y
prohibición de nuevas candidaturas tras el cierre.

**Dependencias:** T037-005.

## T037-007 — Integrar deduplicación y antecedentes por cuenta

**Cubre:** FR-037-006, FR-037-007, SEC-037-001, SEC-037-002; AC-037-003,
AC-037-004.

**Archivos:**

- `src/talentia/shared/application/servicio_principal.py`
- `src/talentia/shared/infrastructure/repositorio_sqlalchemy.py`
- `src/talentia/web/api.py`
- `tests/greenfield/test_convocatorias.py` **(nuevo)**
- `tests/greenfield/test_seguridad.py`
- `tests/greenfield/test_document_extraction.py`

**Trabajo:**

1. Encadenar el alta de candidatura y la carga de CV con deduplicación dentro de la cuenta.
2. Mostrar únicamente proceso, fecha y reclutador de antecedentes autorizados.
3. Evitar creación silenciosa de una segunda identidad cuando la coincidencia sea exacta.
4. Asegurar que búsquedas, URLs y deduplicación no confirmen coincidencias de otra cuenta.
5. Auditar intentos directos fuera de alcance conforme a la política existente.

**Verificación:** coincidencia por documento/correo dentro de cuenta, homónimo sin coincidencia y
misma identidad exclusivamente en otra cuenta sin ninguna filtración.

**Dependencias:** T037-003, T037-005.

## T037-008 — Construir el espacio de trabajo jerárquico

**Cubre:** FR-037-001, FR-037-008, FR-037-009, FR-037-012, NFR-037-004,
NFR-037-006; AC-037-001, AC-037-005, AC-037-007, AC-037-008, AC-037-010.

**Archivos:**

- `src/talentia/web/routes/paginas.py`
- `src/talentia/web/templates/cuentas.html` **(nuevo)**
- `src/talentia/web/templates/convocatorias.html` **(nuevo)**
- `src/talentia/web/templates/detalle_convocatoria.html` **(nuevo)**
- `src/talentia/web/templates/base.html`
- `src/talentia/web/templates/nueva_postulacion.html`
- `src/talentia/web/static/css/aplicacion.css`
- `tests/greenfield/test_operational_forms.py`
- `tests/greenfield/test_operational_panels.py`
- `tests/greenfield/test_frontend_visual.py`

**Trabajo:**

1. Añadir navegación `Cuenta → Perfil → Convocatoria → Responsables → Candidaturas`.
2. Mostrar cupos totales/cubiertos/pendientes, equipo y cantidades por estado.
3. Ofrecer solo transiciones válidas y explicar acciones bloqueadas.
4. Incorporar asignación, selección, vista previa de cierre y confirmación con control humano.
5. Preservar contexto, filtros y comentario tras validaciones o conflictos recuperables.
6. Verificar uso en escritorio, móvil y teclado sin depender solo del color.

**Verificación:** pruebas web y visuales reproducibles, incluida respuesta 409, sin JavaScript de
build ni llamadas a IA.

**Dependencias:** T037-004, T037-006, T037-007.

## T037-009 — Ajustar reportes, exportaciones, auditoría y métricas

**Cubre:** FR-037-012, FR-037-013, SEC-037-005, SEC-037-006; AC-037-005,
AC-037-006, AC-037-007.

**Archivos:**

- `src/talentia/shared/application/servicio_principal.py`
- `src/talentia/shared/infrastructure/repositorio_sqlalchemy.py`
- `src/talentia/web/api.py`
- `tests/greenfield/test_api.py`
- `tests/greenfield/test_seguridad.py`

**Trabajo:**

1. Incorporar convocatoria y cuenta en auditoría, paneles y exportaciones relacionadas.
2. Calcular métricas desde candidaturas y no desde el estado global de candidato.
3. Limitar exportaciones a cuentas autorizadas y minimizar PII.
4. Mantener neutralización de fórmulas para CSV/XLSX.
5. Verificar que altas, cambios y cierres aparecen al recargar todos los módulos relacionados.

**Verificación:** pruebas de conteo, trazabilidad, aislamiento y neutralización de fórmulas.

**Dependencias:** T037-006, T037-008.

## T037-010 — Ejecutar regresión, UAT y cierre de evidencia

**Cubre:** todos los requisitos y AC-037-001 a AC-037-010.

**Archivos:**

- `tests/greenfield/test_convocatorias.py` **(nuevo)**
- pruebas existentes afectadas bajo `tests/greenfield/`
- `specs/037-flujo-cuentas-convocatorias-seleccion/acceptance.md`
- `specs/037-flujo-cuentas-convocatorias-seleccion/review.md` **(nuevo, en fase de revisión)**

**Trabajo:**

1. Ejecutar lint, formato, mypy y toda la suite greenfield.
2. Ejecutar el flujo completo sin claves ni red para demostrar independencia de IA.
3. Probar migración en una copia de una base existente y demostrar downgrade.
4. Ejecutar UAT con dos cuentas, un gestor, dos reclutadoras, perfil reusable, dos convocatorias,
   cuatro candidaturas aptas, dos finalistas, cierre y backups.
5. Registrar evidencia por criterio y cualquier desviación antes de declarar la spec verificada.

**Verificación:** comandos del plan en verde y matriz de evidencia completa, sin criterios omitidos.

**Dependencias:** T037-001 a T037-009.

## Puertas de salida

- [x] Cada requisito funcional, no funcional y de seguridad está cubierto por al menos una tarea.
- [x] Cada criterio AC-037-001 a AC-037-010 tiene una prueba o evidencia reproducible.
- [x] La migración preserva registros y su downgrade fue probado.
- [x] Las consultas y comandos respetan alcance de cuenta en backend.
- [x] El cierre y los cupos resisten escritura concurrente.
- [x] El flujo completo opera sin claves ni proveedores de IA.
- [x] Lint, formato, tipos y suite `tests/greenfield` pasan.
- [x] La implementación no se inicia hasta recibir aprobación explícita del plan y las tareas.


## Registro de implementación — 2026-09-16

- T037-001 a T037-009 implementadas en el monolito modular greenfield.
- T037-010 ejecutada: lint, formato, mypy, migración reversible y regresión completa aprobados.
- Resultado de la suite final: `138 passed`, con cuatro advertencias de dependencias sin fallos.
- Estado entregado a revisión: `VERIFICANDO`; la aprobación final corresponde a `sdd-review-es`.

## Registro de correcciones posteriores a revisión — 2026-09-17

- Se cerraron los siete hallazgos mayores de `verification.md`: compare-and-swap atómico,
  atribución auditada del reclutador, evento IDOR persistente, justificación de finalista, fechas
  obligatorias, contexto/conteos y recuperación web, y prueba integral sin proveedores LLM.
- Se cerraron los hallazgos menores: índice por reclutador de convocatoria, vista acotada para el
  gestor de contratación y deduplicación resuelta en una sola consulta agrupada.
- La migración `0006` conserva downgrade y añade `reclutador_id` nullable para históricos,
  backfill desde auditoría cuando existe e índices de búsqueda por reclutador.
- Verificación continua: `19 passed` en convocatorias+migración; suite final `143 passed`.
- Calidad: Ruff, Ruff format y mypy aprobados. Permanecen cuatro advertencias informativas de
  dependencias; no afectan los criterios de SPEC-037.
- Estado entregado nuevamente a revisión formal: `VERIFICANDO`.
