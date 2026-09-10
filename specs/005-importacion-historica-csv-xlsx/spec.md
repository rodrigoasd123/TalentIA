---
id: SPEC-005
titulo: Importación histórica gobernada desde CSV y XLSX
estado: VERIFICADO
responsable_producto: Usuario
creado: 2026-09-10
actualizado: 2026-09-10
---

# SPEC-005 — Importación histórica gobernada desde CSV y XLSX

## Problema y resultado esperado

TalentIA debe sustituir el seguimiento operativo en hojas de cálculo, pero el ATS actual solo permite registrar vacantes y candidaturas de forma individual. Importar directamente un archivo histórico contaminaría la fuente de verdad con filas inválidas, candidatos repetidos, candidaturas duplicadas o datos sin una base clara de tratamiento.

El resultado esperado es un flujo gobernado que reciba archivos CSV o XLSX, los lleve a un área de preparación en SQLite, permita mapear y validar columnas, clasifique cada fila, muestre una previsualización sin modificar candidatos ni candidaturas y solo confirme las filas elegibles después de una acción humana autorizada. Repetir el mismo archivo o la misma confirmación no debe crear duplicados.

## Usuarios y necesidades

- **Recruiter:** cargar una hoja histórica, mapear columnas, corregir problemas en origen y revisar el resultado antes de importar.
- **HR Manager:** confirmar la importación, resolver excepciones autorizadas y consultar el resumen del lote.
- **Auditor:** reconstruir quién cargó, validó y confirmó un lote sin acceder a más PII de la necesaria.
- **Administrador del laboratorio:** configurar límites técnicos sin obtener acceso implícito al contenido de candidatos.

## Alcance

### Incluido

1. Carga de un archivo `.csv` o `.xlsx` mediante FastAPI y una pantalla Streamlit cliente de la API.
2. Validación de firma/formato, tamaño, número de filas y estructura antes de procesar contenido.
3. Cálculo SHA-256 del archivo y una clave idempotente del lote.
4. Persistencia en SQLite de lote, filas preparadas, mapeo, estado, errores y resumen; el archivo original no será la fuente de verdad.
5. Selección de hoja XLSX y mapeo explícito entre encabezados de origen y campos canónicos.
6. Normalización y validación fila por fila sin insertar candidatos ni candidaturas durante la previsualización.
7. Clasificación de filas como `NEW`, `EXACT_DUPLICATE`, `POSSIBLE_DUPLICATE`, `ALREADY_IN_PROCESS`, `RECONTACT_REVIEW` o `INVALID`.
8. Previsualización paginada con conteos, errores por fila y PII minimizada según permiso.
9. Confirmación humana por HR Manager de las filas elegibles mediante una transacción explícita e idempotente.
10. Creación o reutilización controlada de `Candidate` y creación de `Application` vinculada a una requisición existente.
11. Auditoría de carga, validación, confirmación, filas omitidas y resultado final sin registrar PII en logs técnicos.
12. Pruebas sin red con archivos pequeños y datos completamente ficticios.

### Fuera de alcance

- Importar CV binarios referenciados por rutas de la hoja.
- Crear, aprobar o abrir requisiciones desde el archivo.
- Fusionar automáticamente candidatos posibles duplicados.
- Implementar el módulo completo de proveedores o métricas de Adecco.
- Aplicar reglas definitivas de recontacto no aprobadas por RR. HH.
- Ejecutar matching, rechazo, contacto o cambio automático de pipeline al importar.
- Procesamiento distribuido, colas externas, PostgreSQL o servicios distintos de Python, FastAPI, Streamlit y SQLite.

## Requisitos funcionales

- **FR-001:** El sistema debe aceptar únicamente CSV y XLSX válidos dentro de límites configurables y crear un lote en estado `UPLOADED` asociado al actor, checksum y nombre seguro.
- **FR-002:** El sistema debe rechazar de forma controlada archivos con firma o estructura incompatible, libros cifrados, hojas inexistentes o encabezados duplicados.
- **FR-003:** El sistema debe permitir seleccionar una hoja XLSX y mapear columnas de origen a un esquema canónico sin depender de nombres hardcodeados de una hoja concreta.
- **FR-004:** El esquema canónico debe separar como mínimo candidato, contacto, fuente, requisición, estado histórico y fechas; los campos obligatorios y transformaciones deben mostrarse antes de validar.
- **FR-005:** El sistema debe normalizar y validar cada fila en staging y conservar errores identificados por fila y campo sin modificar las tablas operativas.
- **FR-006:** El sistema debe comparar las filas válidas con candidatos y candidaturas existentes y producir una clasificación explicable con las señales no sensibles utilizadas.
- **FR-007:** El sistema debe mostrar un resumen y una previsualización paginada con totales de filas nuevas, duplicadas, posibles duplicadas, ya vinculadas, sujetas a revisión de recontacto e inválidas.
- **FR-008:** El sistema no debe incluir `POSSIBLE_DUPLICATE`, `RECONTACT_REVIEW` ni `INVALID` en una confirmación automática; esas filas requieren resolución humana fuera de la confirmación estándar.
- **FR-009:** Solo una persona con permiso de confirmación debe poder confirmar un lote en estado `READY_FOR_REVIEW` o `PARTIALLY_VALID`.
- **FR-010:** La confirmación debe crear los candidatos y candidaturas elegibles en una sola transacción y dejar el lote en `IMPORTED`; cualquier fallo debe revertir completamente la escritura operativa.
- **FR-011:** Repetir la carga del mismo contenido o repetir una confirmación con la misma clave idempotente debe devolver el resultado previo sin duplicar candidatos, candidaturas ni eventos de negocio.
- **FR-012:** El sistema debe permitir descargar un reporte de errores sin incluir campos personales no necesarios para corregir el archivo.
- **FR-013:** El sistema debe conservar un historial inmutable de transiciones del lote: `UPLOADED`, `VALIDATING`, `READY_FOR_REVIEW`, `PARTIALLY_VALID`, `REJECTED` e `IMPORTED`.
- **FR-014:** El sistema debe permitir cancelar un lote no confirmado sin borrar su traza de auditoría; la política de purga física se definirá por separado.

## Requisitos no funcionales

- **NFR-001:** La solución debe usar Python, FastAPI, Streamlit, SQLAlchemy y SQLite, respetando las capas `domain`, `application`, `infrastructure` y `api` existentes.
- **NFR-002:** El dominio no debe importar pandas, openpyxl, FastAPI, Streamlit ni SQLAlchemy; la lectura tabular debe quedar detrás de un puerto de infraestructura.
- **NFR-003:** La previsualización y los errores deben paginarse y no deben cargar todo el lote en la respuesta HTTP.
- **NFR-004:** El frontend Streamlit no debe ejecutar validaciones de negocio ni escribir SQLite directamente.
- **NFR-005:** Las operaciones críticas deben aceptar una clave de idempotencia y responder con conflicto controlado ante una versión obsoleta del lote.
- **NFR-006:** La suite obligatoria debe ejecutarse sin red y cubrir parser CSV/XLSX, normalización, transacción, autorización, idempotencia y regresión.
- **NFR-007:** Los límites de archivo y filas deben residir en configuración y tener valores conservadores para el laboratorio local.
- **NFR-008:** La importación no debe bloquear el uso normal del ATS durante la validación de un lote permitido para el piloto local.

## Seguridad y privacidad

- **SEC-001:** Todo endpoint de importación debe autenticar y autorizar; cargar, visualizar PII, confirmar y auditar deben ser permisos separados.
- **SEC-002:** El sistema debe validar el contenido real y la expansión del XLSX, no solo su extensión, y debe disponer de un punto de integración para análisis antimalware.
- **SEC-003:** Los archivos y celdas se consideran entrada no confiable; fórmulas, enlaces, macros e instrucciones incrustadas no deben ejecutarse ni controlar el sistema.
- **SEC-004:** La lectura XLSX debe usar valores almacenados, desactivar enlaces externos y rechazar macros o formatos no admitidos.
- **SEC-005:** Los logs técnicos deben registrar identificadores de lote, conteos, duración y resultado, pero nunca filas completas, documentos, correos, teléfonos ni identificadores nacionales.
- **SEC-006:** La previsualización y el reporte de errores deben aplicar minimización y enmascarado según permiso.
- **SEC-007:** Ninguna fila debe crear una candidatura sin una requisición existente y autorizada ni debe saltarse las reglas del dominio.
- **SEC-008:** Ninguna decisión de contratación, descarte, contacto o matching debe derivarse de la importación.
- **SEC-009:** Las pruebas y fixtures solo pueden contener identidades ficticias evidentes.
- **SEC-010:** El archivo temporal debe almacenarse bajo una clave generada, fuera de rutas servidas, y eliminarse al finalizar según la política aprobada; el nombre original nunca debe usarse como ruta.

## Reglas y fuentes de verdad

- `Candidate` representa una persona; `Application` representa su participación en una requisición.
- La base SQLite del ATS es la fuente de verdad después de una confirmación exitosa; el archivo importado nunca sobrescribe silenciosamente datos existentes.
- Los estados y permisos del dominio prevalecen sobre cualquier valor de una celda.
- El checksum del archivo identifica contenido repetido; una clave de idempotencia identifica un intento lógico de confirmación.
- Un posible duplicado se revisa, nunca se fusiona automáticamente.
- Los eventos de auditoría y el historial del lote son append-only desde la aplicación.

## Supuestos confirmados

- El piloto permanece local, de una sola empresa y con datos ficticios.
- SQLite es la base de datos autorizada y la solución solo utilizará Python, FastAPI y Streamlit.
- La primera iteración importa metadatos; no recupera CV desde rutas o enlaces incluidos en la hoja.
- El frontend continuará consumiendo la API y no accederá directamente a la base.

## Riesgos y fallos esperados

- **Hojas inconsistentes:** encabezados y tipos varían entre archivos. Mitigación: mapeo explícito y staging antes de confirmar.
- **Duplicados silenciosos:** datos normalizados pueden coincidir parcialmente. Mitigación: clasificación explicable y revisión humana de casos ambiguos.
- **Fórmulas maliciosas o CSV injection:** una celda podría interpretarse como fórmula al exportar. Mitigación: tratar entradas como texto y sanear reportes descargables.
- **Consumo de memoria:** pandas puede materializar libros completos. Mitigación: límites configurables, lectura controlada y respuestas paginadas.
- **Consentimiento histórico incierto:** la hoja puede no probar una base vigente de tratamiento. Mitigación: no activar ni procesar automáticamente registros sin la regla aprobada.
- **Transacción extensa en SQLite:** confirmar demasiadas filas puede bloquear escrituras. Mitigación: límite conservador del piloto y transacción única medida; lotes grandes quedan fuera hasta contar con evidencia.

## Preguntas abiertas

No quedan preguntas bloqueantes. La directiva de ejecución del 2026-09-10 aprobó
el tratamiento restringido, los identificadores fuertes configurables, el mapeo
sin formato TCS fijo y los límites iniciales configurables.

## Historial de decisiones

| Fecha | Decisión | Responsable | Motivo |
|---|---|---|---|
| 2026-09-10 | Se adopta Python + FastAPI + Streamlit + SQLite y se descarta para esta implementación el stack Java/React/PostgreSQL del plan maestro. | Usuario | Restricción técnica explícita del usuario. |
| 2026-09-10 | La siguiente capacidad P0 propuesta es la importación histórica CSV/XLSX. | Equipo de implementación | Es la brecha P0 observable necesaria para sustituir Excel sin duplicar capacidades ya verificadas en SPEC-004. |
| 2026-09-10 | La especificación permanece en BORRADOR y no autoriza implementación. | Equipo de implementación | Existen decisiones de datos y alcance que requieren aprobación humana según el flujo SDD. |
| 2026-09-10 | Los registros sin estado legal conocido se importan como `RESTRICTED_REVIEW`; no participan en IA, rediscovery, contacto automático ni intercambio con proveedores. | Usuario | Directiva de ejecución aprobada. |
| 2026-09-10 | Documento, correo normalizado o teléfono normalizado son identificadores fuertes; nombre solo exige revisión manual en staging. | Usuario | Evitar rechazo silencioso y candidatos definitivos ambiguos. |
| 2026-09-10 | Se aprueban sugerencias automáticas, mapeo manual y plantillas reutilizables, sin formato TCS fijo. | Usuario | Adaptarse a fuentes históricas heterogéneas. |
| 2026-09-10 | Los límites iniciales son 20 MB y 10 000 filas, configurables por entorno. | Usuario | Directiva de ejecución aprobada. |
| 2026-09-10 | La SPEC pasa por `LISTO` a `IMPLEMENTANDO`; el plan queda aprobado por la directiva que ordena implementar SPEC-005. | Usuario | La implementación, pruebas, migraciones y documentación están autorizadas explícitamente. |
| 2026-09-10 | Los futuros AI Agents usarán LangGraph, MLflow Tracing central y un puerto `LLMProvider` con Gemini inicial; no se crean agentes en SPEC-005. | Usuario | Nueva restricción permanente que conserva como deterministas la importación, deduplicación exacta, RBAC, auditoría y transacciones. |
| 2026-09-10 | La SPEC pasa a `VERIFICANDO` tras completar T-001–T-007. | Equipo de implementación | Se ejecutan criterios, regresión, migración, seguridad, lint y tipado focal. |
| 2026-09-10 | La SPEC pasa a `VERIFICADO`. | Equipo de revisión | AC-001–AC-008 aprobados sin hallazgos críticos o mayores dentro del alcance. |
