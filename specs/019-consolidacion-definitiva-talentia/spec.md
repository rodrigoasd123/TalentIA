# SPEC-019 — Consolidación definitiva de TalentIA

## Estado

**Implementada y verificada localmente.** La publicación a GitHub fue autorizada
por el usuario el 10 de septiembre de 2026.

## Contexto

TalentIA reúne hoy dos líneas históricas: el ATS gobernado identificado
internamente como VERA y el analizador documental PostulaIA. La interfaz principal
ya usa parcialmente la marca TalentIA, pero la API, configuración, base de datos,
scripts, fixtures, documentación y entrypoints heredados todavía presentan esos
nombres como productos independientes.

El repositorio también conserva un frontend documental separado y módulos
heredados de PDF, OCR, ranking, embeddings, caché y RAG. La consolidación debe
integrarlos como capacidades internas sin duplicarlos, eliminar la identidad
visible fragmentada y preservar datos e identificadores que tengan valor de
compatibilidad o auditoría.

## Coordinación y numeración

Después de ejecutar `git fetch --all --prune` se revisaron `origin/main`,
`origin/agenteAI`, `origin/codex/talentia-streamlit-ux-20260910` y las specs de cada
rama. `SPEC-018` está ocupada por la base general de candidatos. La rama paralela
detectada modifica `.github/workflows/ci.yml` y no contiene una nueva spec. Por
tanto, el siguiente número libre observado es **SPEC-019** y no existe colisión de
numeración o archivos al redactar este borrador.

No se integrará ni modificará la rama paralela dentro de esta funcionalidad. Si
antes de implementar aparece otra `SPEC-019` remota o solapamiento material, el
trabajo deberá detenerse para coordinación.

## Inventario de referencias heredadas

### Referencias visibles que deben adoptar TalentIA

- Metadatos y mensajes de ciclo de vida de FastAPI (`VERA ATS`).
- Textos de ayuda del proveedor, configuración, demo y laboratorio.
- Títulos de los entrypoints `streamlit_postulacion.py` y
  `frontend/streamlit_postulacion.py` mientras continúen accesibles.
- README, manual vigente, contexto SDD, fixtures activos y textos de laboratorio.
- Nombre y descripción públicos del paquete, Docker Compose y CI.
- Usuarios y credenciales ficticias de laboratorio cuando el cambio no afecte
  instalaciones reales.
- Cualquier navegación que presente VERA o PostulaIA como una aplicación separada
  o como un rollback visible para el usuario.

### Identificadores técnicos migrables con compatibilidad

- Variables oficiales `TALENTIA_*`, manteniendo aliases temporales `VERA_*`.
- Base predeterminada `talentia.db`, con adopción segura de `vera.db`.
- Nombre y descripción de distribución `vera-ats` cuando el análisis de dependencias
  confirme que el cambio no rompe instalaciones.
- Emisor JWT, nombre del agente, User-Agent, nombres de métricas y valores por
  defecto de auditoría únicamente mediante lectura dual o alias durante la ventana
  de transición.
- `.vera_dev_key` únicamente si se conserva lectura compatible y migración segura
  a un nombre TalentIA.

### Referencias históricas que deben conservarse

- Revisiones, nombres y contenido histórico de migraciones Alembic ya publicadas.
- Specs archivadas, ADR y evidencia histórica cuando el nombre explique una decisión
  tomada en ese momento.
- Valores VERA/PostulaIA ya persistidos en eventos de auditoría, trazas, ejecuciones
  o registros: son evidencia y no se reescriben.
- Salt criptográfico `vera-ats-kdf-salt-v1` y material necesario para descifrar
  secretos existentes, salvo migración criptográfica separada y demostrablemente
  reversible.
- Identificadores de emisor JWT durante la vida máxima de tokens heredados.
- Rutas de módulo como `postulaia_ocr.py`, nombres de caché o grafo y contratos
  importados cuando renombrarlos no aporte valor visible y aumente el riesgo.

## Objetivo

Consolidar identidad, configuración, persistencia y navegación para que el único
producto visible sea **TalentIA**, manteniendo una sola fuente SQL de verdad y
conservando todas las capacidades actuales del ATS y del analizador documental.

## Alcance funcional

### Identidad unificada

- **FR-019-001:** títulos, encabezados, navegación, metadatos, ayuda y documentación
  vigente deben presentar exclusivamente el nombre TalentIA.
- **FR-019-002:** no debe existir navegación a una aplicación separada llamada VERA,
  VERA ATS, PostulaIA o PostulAI.
- **FR-019-003:** los nombres heredados solo podrán aparecer en documentación
  histórica o mensajes técnicos de compatibilidad claramente identificados como
  legado, nunca como marca activa.
- **FR-019-004:** los cambios visuales se limitarán a identidad y navegación mínima;
  no implementarán un nuevo rediseño visual.

### Aplicación única y capacidades conservadas

- **FR-019-005:** FastAPI seguirá siendo la única puerta de entrada a reglas de
  negocio y Streamlit continuará consumiendo la API.
- **FR-019-006:** TalentIA conservará vacantes, candidatos, versiones de CV,
  postulaciones, evaluaciones, revisión humana, pipeline, Candidate 360,
  comunicaciones, importación histórica, dashboard, reportes, auditoría y
  configuración.
- **FR-019-007:** lectura PDF, OCR, filtros, ranking documental, embeddings, caché
  vectorial, caché de respuestas y consulta RAG se expondrán como módulos internos
  desde la navegación principal.
- **FR-019-008:** la integración reutilizará los motores existentes mediante API o
  adaptadores; no creará un segundo extractor, OCR, recuperador, ranking o caché.
- **FR-019-009:** el entrypoint documental separado dejará de ser una opción visible.
  Podrá conservarse temporalmente como rollback técnico documentado y no enlazado.
- **FR-019-010:** Excel y CSV solo serán entradas de importación histórica o salidas
  controladas; ninguna hoja será fuente de verdad después de confirmar una carga.

### Configuración oficial y aliases

- **FR-019-011:** todas las opciones estáticas tendrán un nombre oficial
  `TALENTIA_*`, incluidos entorno, base, secretos, API, almacenamiento, límites,
  flags y observabilidad.
- **FR-019-012:** el alias equivalente `VERA_*` continuará funcionando durante una
  ventana de transición documentada.
- **FR-019-013:** cuando existan ambos nombres, `TALENTIA_*` tendrá prioridad aunque
  el alias heredado tenga otro valor.
- **FR-019-014:** el uso de un alias heredado emitirá una advertencia con el nombre
  de la variable, nunca con su valor.
- **FR-019-015:** `.env.example`, Docker, CI, scripts y documentación usarán los
  nombres oficiales y no contendrán secretos reales.
- **FR-019-016:** la retirada de aliases requerirá una versión mayor posterior y un
  periodo mínimo documentado de dos versiones menores estables.

### Base de datos SQLite y conservación

- **FR-019-017:** una instalación nueva usará `sqlite:///./talentia.db` y Alembic
  seguirá gobernando el esquema.
- **FR-019-018:** al usar la ubicación SQLite predeterminada, si existe `vera.db` y
  no existe `talentia.db`, el arranque ejecutará una adopción segura antes de abrir
  el motor.
- **FR-019-019:** antes de adoptar `vera.db` se creará un respaldo verificable en la
  misma unidad, se calculará SHA-256 y se comprobarán `PRAGMA integrity_check`, la
  revisión Alembic y los conteos de tablas críticas.
- **FR-019-020:** el cambio de nombre final será atómico; después se ejecutarán las
  migraciones Alembic pendientes y se volverán a verificar integridad, revisión y
  conteos.
- **FR-019-021:** si existen ambas bases, ninguna se abrirá ni sobrescribirá
  automáticamente. El arranque fallará con rutas y pasos accionables, sin exponer
  datos internos.
- **FR-019-022:** si falla respaldo, verificación, cambio atómico o migración, el
  sistema no iniciará y restaurará el estado anterior cuando sea seguro hacerlo.
- **FR-019-023:** una URL de base configurada explícitamente no se moverá ni renombrará
  fuera del procedimiento explícito documentado.
- **FR-019-024:** no se editarán migraciones publicadas ni se ejecutará
  `seed.py --reset` sobre una base adoptada.
- **FR-019-025:** el procedimiento de reversión conservará el respaldo, documentará
  el hash y nunca reemplazará una ruta que ya contenga otra base.

### Candidatos y estado de selección

- **FR-019-026:** una persona podrá conservar datos personales, consentimiento,
  base legal, varias versiones de CV, múltiples postulaciones, evaluaciones por
  postulación, revisiones, comunicaciones, historial y auditoría.
- **FR-019-027:** `Application.status` será la única fuente canónica del estado de
  selección para una vacante concreta.
- **FR-019-028:** el campo `Candidate.candidate_status` introducido anteriormente se
  tratará como compatibilidad transitoria y no gobernará decisiones, métricas ni
  automatizaciones. Sus valores existentes no se eliminarán.
- **FR-019-029:** la interfaz que necesite mostrar un estado general deberá derivarlo
  de las postulaciones o exigir contexto de vacante. Los casos ambiguos con varias
  postulaciones requerirán revisión humana; no se migrarán automáticamente a un
  único estado.
- **FR-019-030:** la detección de duplicados continuará siendo conservadora y toda
  fusión de personas requerirá aprobación humana.

## Seguridad, privacidad y gobierno

- **SEC-019-001:** RBAC permanecerá en denegación por defecto y cada endpoint nuevo
  declarará permisos explícitos.
- **SEC-019-002:** ninguna migración o advertencia registrará PII, secretos, tokens,
  contraseñas, claves o contenido de documentos.
- **SEC-019-003:** documentos y archivos importados seguirán tratándose como contenido
  no confiable y conservarán límites, validaciones y guardrails.
- **SEC-019-004:** las decisiones laborales y fusiones conservarán revisión humana;
  esta spec no habilitará envíos externos, scraping ni acciones irreversibles.
- **SEC-019-005:** fixtures y pruebas utilizarán solo datos ficticios.
- **SEC-019-006:** la consolidación no debilitará cifrado, enmascaramiento de secretos,
  cadena de auditoría ni separación de PII previa a evaluación.
- **SEC-019-007:** se documentarán como brechas fuera de alcance las políticas aún no
  implementadas de cifrado integral de PII en reposo, retención, eliminación y
  respaldo operativo.

## Arquitectura y compatibilidad

- **NFR-019-001:** se mantendrá separación entre dominio, aplicación,
  infraestructura, API y presentación.
- **NFR-019-002:** SQLAlchemy seguirá aislando la persistencia y el diseño no impedirá
  migrar posteriormente a PostgreSQL; esta spec no realizará esa migración.
- **NFR-019-003:** los adaptadores heredados podrán mantener nombres internos cuando
  el renombrado rompa imports, cachés o evidencia sin beneficio funcional.
- **NFR-019-004:** nuevos tokens y eventos usarán identidad TalentIA; lectores y
  verificadores aceptarán identificadores heredados solo durante la ventana de
  compatibilidad necesaria.
- **NFR-019-005:** las operaciones de adopción de base serán idempotentes, observables
  y seguras ante interrupciones.
- **NFR-019-006:** no se sobrescribirán cambios no relacionados ni se resolverán
  conflictos de la rama paralela alterando su funcionalidad.

## Fuera de alcance

- PostgreSQL o despliegue administrado.
- Rediseño visual integral.
- Reescritura de OCR, RAG, ranking, embeddings o cachés.
- Reescritura de migraciones, auditorías o specs históricas.
- Envío externo automático, scraping o automatización de decisiones laborales.
- Cifrado integral nuevo de todas las columnas PII, política corporativa de retención
  y sistema de backups operativos; se documentarán sus brechas.

## Riesgos abiertos que el plan deberá resolver después de la aprobación

- Compatibilidad criptográfica de `.vera_dev_key`, la variable maestra y el salt KDF.
- Ventana exacta de aceptación del emisor JWT heredado sin ampliar la validez de tokens.
- Conciliación manual del `candidate_status` previo cuando una persona tenga varias
  postulaciones.
- Integración del RAG heredado detrás de FastAPI sin duplicar lógica en Streamlit.
- Prueba de rollback ante fallos inyectados en cada fase de adopción de SQLite.
