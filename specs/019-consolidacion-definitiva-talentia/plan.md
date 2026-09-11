# SPEC-019 — Plan de implementación

## Estado

**Aprobado e implementado.** La publicación se autorizó tras la verificación local.

## Principios de ejecución

1. Trabajar sobre `agenteAI` sin integrar ni modificar la rama paralela.
2. Volver a ejecutar `git fetch --all --prune` antes del primer cambio de código y
   detenerse si aparece otra SPEC-019 o un solapamiento material.
3. Preservar las migraciones Alembic, auditorías e identificadores históricos.
4. Preferir aliases y adaptadores sobre renombrados internos de alto riesgo.
5. No tocar una base real del usuario durante pruebas; todos los escenarios usarán
   directorios temporales y datos ficticios.
6. No publicar en GitHub hasta completar la verificación y recibir autorización.

## Arquitectura objetivo

```text
Streamlit TalentIA
       │ HTTP
       ▼
FastAPI TalentIA ─────► Casos de uso ATS ─────► SQLAlchemy/Alembic/SQLite
       │
       └──────────────► Adaptador documental interno
                              │
                              ├─ PDF / OCR
                              ├─ filtros / ranking
                              ├─ embeddings / cachés
                              └─ consulta RAG
```

Streamlit solo presentará datos y enviará comandos a FastAPI. Los componentes
documentales heredados permanecerán reutilizables detrás de un adaptador de
aplicación y endpoints gobernados; no se copiará su lógica a la interfaz.

## Fase 0 — Salvaguardas y línea base

- Actualizar referencias remotas y comparar nombres de spec y archivos afectados.
- Capturar `git status`, commit base y diff de la rama paralela.
- Ejecutar la suite actual, smoke de FastAPI/Streamlit y escáner del repositorio.
- Generar un inventario reproducible de referencias heredadas clasificado en:
  visible, migrable, histórico y compatibilidad obligatoria.
- Crear una allowlist revisable para coincidencias históricas legítimas.

No se avanzará si la línea base falla de manera reproducible o si aparece una
colisión no coordinada.

## Fase 1 — Configuración TalentIA con compatibilidad VERA

### Resolución de variables

Se añadirá una capa de normalización previa a `Settings`:

1. Para cada campo se buscará primero `TALENTIA_<CAMPO>`.
2. Si no existe, se buscará `VERA_<CAMPO>`.
3. El valor elegido se pasará al modelo de configuración sin escribirlo en logs.
4. Por cada alias utilizado se emitirá una sola advertencia con los nombres de las
   variables, nunca con valores.

La normalización cubrirá todas las opciones estáticas, no solo la base de datos.
La API client conservará la misma prioridad. Los tests limpiarán explícitamente el
entorno para evitar falsos positivos por variables del host.

### Secretos y compatibilidad criptográfica

- El nombre oficial será `TALENTIA_SECRET_KEY` y el alias `VERA_SECRET_KEY` seguirá
  siendo aceptado.
- La derivación criptográfica conservará el salt histórico para poder descifrar
  valores ya persistidos; se documentará que el texto del salt es un identificador
  técnico, no marca visible.
- Se introducirá `.talentia_dev_key` para instalaciones nuevas.
- Si solo existe `.vera_dev_key`, se adoptará de forma segura sin regenerar la clave.
- Si existen ambos archivos con contenidos distintos, el arranque se detendrá; no
  se elegirá uno arbitrariamente.
- El emisor oficial de nuevos JWT será TalentIA. La validación aceptará el emisor
  heredado únicamente durante la vida máxima configurada de tokens emitidos antes
  de la actualización, sin extender expiraciones.

### Distribución

Se actualizarán `.env.example`, Docker Compose, CI y comandos vigentes a
`TALENTIA_*`. Los aliases se documentarán como obsoletos por al menos dos versiones
menores estables y retirables solo en una versión mayor.

## Fase 2 — Adopción segura de `talentia.db`

### Componente

Crear un servicio de infraestructura aislado, sin importar FastAPI ni Streamlit,
responsable de inspeccionar y adoptar únicamente las rutas SQLite predeterminadas.
El servicio expondrá un resultado estructurado y errores accionables.

### Algoritmo

1. Determinar si la URL fue configurada explícitamente. Si lo fue, no mover archivos.
2. Resolver rutas absolutas de `vera.db` y `talentia.db` dentro del directorio de
   trabajo configurado.
3. Si no existe ninguna, continuar con `talentia.db`.
4. Si solo existe `talentia.db`, verificarla y continuar.
5. Si existen ambas, detenerse antes de crear motor o abrir sesión.
6. Si solo existe `vera.db`:
   - abrir en modo lectura y ejecutar `PRAGMA integrity_check`;
   - leer revisión Alembic y conteos de tablas críticas;
   - calcular SHA-256;
   - copiar a un archivo temporal exclusivo en la misma unidad;
   - sincronizar y verificar que hash, integridad, revisión y conteos coinciden;
   - conservar una copia de respaldo con nombre único y manifiesto sin PII;
   - promover el temporal a `talentia.db` mediante `os.replace`;
   - ejecutar Alembic sobre `talentia.db`;
   - verificar nuevamente integridad, revisión y conteos no decrecientes.
7. Solo después de todas las verificaciones se iniciará el motor normal.

`vera.db` no se eliminará automáticamente. La adopción será por copia verificada,
lo que conserva el origen y simplifica la reversión. Los temporales incompletos se
identificarán por nombre controlado y solo se limpiarán después de validar que están
dentro del directorio esperado.

### Fallos y reversión

- Antes de la promoción: eliminar únicamente el temporal validado; conservar origen.
- Después de la promoción y antes de completar Alembic: detener el arranque, conservar
  ambas evidencias y ofrecer el comando de restauración seguro.
- La restauración verificará el hash del respaldo y exigirá que el destino no exista.
- Los fallos se probarán mediante puntos de inyección, no corrompiendo archivos reales.

No se añadirá una migración Alembic para renombrar el archivo: Alembic gobierna el
esquema interno, mientras que la adopción del archivo ocurre antes de crear el motor.
Las revisiones publicadas permanecerán inmutables.

## Fase 3 — Identidad visible TalentIA

- Cambiar título, descripción y logs de ciclo de vida de FastAPI.
- Cambiar textos activos del agente, configuración, errores, demo, fixtures y
  usuarios ficticios de laboratorio.
- Actualizar nombre y descripción del paquete solo después de verificar que no hay
  consumidores internos del nombre de distribución.
- Actualizar README, manual, contexto y constitución vigentes sin reescribir specs
  archivadas ni ADR históricos.
- Mantener nombres internos heredados en una allowlist cuando sean necesarios para
  imports, criptografía, métricas históricas o trazabilidad.

Los mensajes de compatibilidad usarán expresiones como “variable heredada” sin
presentar VERA o PostulaIA como productos disponibles.

## Fase 4 — Integración del analizador documental

### Backend

- Inventariar contratos vigentes de `backend/`, `agente_postulacion/` y el adaptador
  OCR ya usado por el ATS.
- Seleccionar una implementación canónica por capacidad.
- Crear un servicio de aplicación TalentIA que coordine perfil, documentos,
  extracción, ranking, recuperación y consulta con evidencia.
- Reutilizar cachés y embeddings existentes a través de adaptadores; mantener claves
  de caché compatibles cuando contengan datos ya calculados.
- Exponer endpoints FastAPI con esquemas tipados, límites de archivo, permisos y
  neutralización de contenido no confiable.
- Mantener el agente como asistente explicativo: no cambia estados, no contacta y no
  decide contrataciones.

### Frontend

- Incorporar la capacidad documental como una página de la navegación principal.
- La página consumirá exclusivamente los endpoints FastAPI.
- Retirar enlaces o instrucciones al frontend separado.
- Mantener el entrypoint heredado no enlazado solo como rollback técnico temporal,
  con procedimiento para retirarlo después de la estabilización.

## Fase 5 — Estado de candidatos y fuente SQL

- Mantener `Application.status` como estado canónico por vacante.
- Dejar de usar `Candidate.candidate_status` para decisiones, métricas o reportes de
  selección.
- Conservar la columna y sus valores existentes como dato legado, sin migración
  destructiva.
- Adaptar la ficha general para mostrar las postulaciones y sus estados por vacante.
- Cuando exista una sola postulación, podrá mostrarse un resumen derivado claramente
  rotulado; con varias postulaciones nunca se colapsarán estados automáticamente.
- Mantener auditoría, bloqueo optimista y detección conservadora de duplicados.
- Confirmar que importaciones CSV/XLSX desembocan en SQL y que las ediciones
  posteriores no leen la hoja original.

## Fase 6 — Documentación y operación

- Documentar instalación nueva, aliases, precedencia y fecha mínima de retiro.
- Documentar adopción de `vera.db`, conflicto de dos bases, manifiesto/hash,
  diagnóstico y reversión.
- Documentar el rollback técnico del entrypoint documental sin ofrecerlo en UI.
- Documentar brechas fuera de alcance: cifrado completo de PII en reposo, retención,
  eliminación y backups operativos.
- Actualizar mapa funcional y catálogo de specs únicamente al cerrar la implementación.

## Estrategia de pruebas

### Unitarias

- Matriz completa `TALENTIA_*`, aliases `VERA_*`, precedencia y advertencias seguras.
- Resolución/adopción de claves de desarrollo.
- Servicio de adopción SQLite para cada estado y punto de fallo.
- Derivación de estados de postulación sin depender de `candidate_status`.
- Adaptadores documentales y preservación de evidencia/caché.

### Integración

- Instalación nueva con `talentia.db`.
- Adopción de una base `vera.db` con datos ficticios en todas las tablas críticas.
- Base `talentia.db` existente.
- Conflicto con ambas bases.
- Fallos antes y después de la promoción y reversión verificada.
- Upgrade Alembic desde la revisión publicada hasta `head` sin editar migraciones.
- Endpoints documentales bajo RBAC y límites de archivos.

### Regresión y smoke

- Suite ATS completa.
- Suite heredada de PDF, OCR, moderación, ranking, RAG, embeddings y cachés.
- FastAPI: arranque, OpenAPI, salud y rutas principales.
- Streamlit: importación de todas las páginas y sesión supervisada.
- Escáner de secretos, PII y artefactos prohibidos.
- Búsqueda visible automatizada con allowlist histórica.
- Capturas de las superficies principales para confirmar que solo muestran TalentIA.

## Trazabilidad de aceptación

| Grupo de criterios | Fases responsables |
|---|---|
| AC-019-001 a AC-019-003 | 0, 3 y 6 |
| AC-019-004 a AC-019-006 | 4, 5 y regresión |
| AC-019-007 a AC-019-010 | 1 y 6 |
| AC-019-011 a AC-019-018 | 2 y pruebas de integración |
| AC-019-019 a AC-019-021 | 5 |
| AC-019-022 a AC-019-024 | Todas las fases y escáner |
| AC-019-025 | Verificación final |

## Estrategia de commits

Mantener cambios separados y revisables:

1. configuración y compatibilidad;
2. adopción segura de SQLite;
3. identidad visible y documentación;
4. integración documental FastAPI/Streamlit;
5. estado por postulación y regresiones;
6. evidencia final de la spec.

No se hará push durante estas fases. La publicación requerirá autorización explícita
después de que `verification.md` contenga evidencia suficiente.
