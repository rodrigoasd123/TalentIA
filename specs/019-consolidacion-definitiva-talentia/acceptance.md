# SPEC-019 — Criterios de aceptación

## Estado

**Implementada; evidencia registrada en `verification.md`.**

## Identidad y navegación

### AC-019-001 — Marca visible única

**Dado** un arranque limpio de FastAPI y Streamlit  
**Cuando** se recorren metadatos, login, navegación, pantallas, ayudas y errores  
**Entonces** el único nombre de producto mostrado es TalentIA  
**Y** no aparecen VERA, VERA ATS, PostulaIA ni PostulAI como marcas activas.

### AC-019-002 — Aplicación única

**Dado** un usuario con permisos para todas las capacidades  
**Cuando** navega por TalentIA  
**Entonces** accede desde la navegación principal al ATS y a análisis documental,
OCR, ranking y consulta RAG  
**Y** no existe enlace a un frontend separado ni mensaje de rollback a otra aplicación.

### AC-019-003 — Historia preservada

**Dado** el repositorio consolidado  
**Cuando** se ejecuta el detector automatizado de nombres heredados  
**Entonces** cada coincidencia restante pertenece a una allowlist justificada de
migración publicada, evidencia histórica, compatibilidad criptográfica, import o
identificador persistido  
**Y** ninguna coincidencia permitida se presenta al usuario como producto vigente.

## Capacidades y arquitectura

### AC-019-004 — Regresión ATS

**Dado** el conjunto de pruebas del ATS  
**Cuando** se ejecuta después de la consolidación  
**Entonces** siguen operativas vacantes, candidatos, CV versionados, postulaciones,
evaluaciones, revisión humana, pipeline, Candidate 360, comunicaciones, importación,
dashboard, reportes, auditoría y configuración.

### AC-019-005 — Regresión documental

**Dado** el conjunto de fixtures ficticios PDF, incluidos documentos escaneados  
**Cuando** se ejecutan lectura, OCR, filtros, ranking, embeddings, caché vectorial,
caché de respuestas y RAG  
**Entonces** conservan sus contratos y evidencia  
**Y** la implementación reutiliza los motores existentes sin duplicarlos.

### AC-019-006 — Límites de capas

**Dado** el análisis de arquitectura  
**Cuando** se inspeccionan imports y flujos  
**Entonces** Streamlit no accede a SQLAlchemy ni replica reglas de negocio  
**Y** toda operación funcional pasa por FastAPI y las capas de aplicación/dominio.

## Configuración

### AC-019-007 — Configuración oficial

**Dado** únicamente variables `TALENTIA_*`  
**Cuando** inicia la aplicación  
**Entonces** todas las opciones estáticas se cargan con sus valores oficiales  
**Y** ningún secreto aparece en salida, logs o respuestas.

### AC-019-008 — Compatibilidad heredada

**Dado** únicamente una variable `VERA_*` válida  
**Cuando** inicia la aplicación durante la ventana de transición  
**Entonces** se utiliza su valor  
**Y** se emite una advertencia que muestra solo el nombre obsoleto y su reemplazo.

### AC-019-009 — Prioridad TalentIA

**Dado** `TALENTIA_DATABASE_URL` y `VERA_DATABASE_URL` con valores diferentes  
**Cuando** se construye la configuración  
**Entonces** prevalece `TALENTIA_DATABASE_URL`  
**Y** no se revela ninguno de los valores en la advertencia.

### AC-019-010 — Distribución segura

**Dado** `.env.example`, Docker Compose, CI, scripts y documentación  
**Cuando** se inspeccionan  
**Entonces** usan `TALENTIA_*` como nombres oficiales  
**Y** el escáner no encuentra secretos, PII real ni bases versionadas.

## Adopción segura de SQLite

### AC-019-011 — Instalación nueva

**Dado** que no existe `vera.db` ni `talentia.db` y no se configuró otra URL  
**Cuando** inicia TalentIA  
**Entonces** crea `talentia.db`, aplica Alembic hasta `head` y no crea `vera.db`.

### AC-019-012 — Base heredada existente

**Dado** un `vera.db` válido con candidatos, vacantes, postulaciones, documentos,
evaluaciones, revisiones y auditoría, y ausencia de `talentia.db`  
**Cuando** inicia TalentIA  
**Entonces** crea un respaldo verificable y registra su SHA-256 sin datos sensibles  
**Y** adopta la base mediante una operación atómica  
**Y** conserva revisión Alembic, integridad referencial y los conteos de todas las
tablas críticas  
**Y** finaliza usando `talentia.db`.

### AC-019-013 — Base TalentIA existente

**Dado** un `talentia.db` válido y ausencia de `vera.db`  
**Cuando** inicia la aplicación  
**Entonces** usa esa base, aplica solo migraciones pendientes y no crea copias
heredadas innecesarias.

### AC-019-014 — Conflicto de dos bases

**Dado** que existen `vera.db` y `talentia.db`  
**Cuando** inicia la aplicación con la ubicación predeterminada  
**Entonces** se detiene antes de abrir o modificar cualquiera  
**Y** muestra un mensaje accionable con las rutas involucradas y el procedimiento
manual  
**Y** no sobrescribe, fusiona ni elimina archivos.

### AC-019-015 — Fallo antes del cambio atómico

**Dado** un fallo inyectado durante copia, hash o verificación previa  
**Cuando** se intenta adoptar `vera.db`  
**Entonces** `vera.db` permanece utilizable, no aparece una `talentia.db` parcial y
el arranque falla de forma segura.

### AC-019-016 — Fallo durante o después del cambio

**Dado** un fallo inyectado durante el cambio atómico, Alembic o verificación final  
**Cuando** se ejecuta la adopción  
**Entonces** existe un camino probado de reversión desde el respaldo verificado  
**Y** ninguna base preexistente es sobrescrita  
**Y** el proceso puede reintentarse de manera idempotente después de resolver el
fallo.

### AC-019-017 — URL explícita

**Dado** que la base se configuró mediante una URL explícita  
**Cuando** inicia TalentIA  
**Entonces** no renombra ni mueve ese archivo automáticamente  
**Y** Alembic opera únicamente sobre la URL efectiva autorizada.

### AC-019-018 — Reversión documentada

**Dado** una adopción completada  
**Cuando** un operador sigue el procedimiento de reversión  
**Entonces** puede volver al archivo respaldado verificando su hash y revisión  
**Y** el procedimiento se niega a reemplazar un destino ocupado.

## Candidatos y fuente de verdad

### AC-019-019 — Estado por postulación

**Dado** una persona con dos postulaciones en estados diferentes  
**Cuando** se consulta su ficha  
**Entonces** cada estado se muestra asociado a su vacante  
**Y** ningún campo general de candidato sustituye esos estados.

### AC-019-020 — Compatibilidad de estado general previo

**Dado** un registro existente con `candidate_status`  
**Cuando** se ejecuta la consolidación  
**Entonces** su valor original se conserva para trazabilidad  
**Y** no alimenta decisiones, transiciones, métricas ni automatizaciones  
**Y** los casos ambiguos se señalan para revisión humana sin migración destructiva.

### AC-019-021 — SQL como fuente de verdad

**Dado** un lote Excel o CSV confirmado  
**Cuando** se modifica posteriormente la persona o su postulación  
**Entonces** la modificación se realiza en TalentIA y queda auditada en SQL  
**Y** la hoja original no se consulta como fuente operativa.

## Seguridad y privacidad

### AC-019-022 — RBAC y PII

**Dado** cada rol del sistema  
**Cuando** intenta usar capacidades ATS y documentales  
**Entonces** se aplica denegación por defecto y los permisos existentes  
**Y** logs, errores y auditoría no contienen PII ni secretos.

### AC-019-023 — Gobierno de decisiones

**Dado** una evaluación, comunicación sensible o posible fusión de duplicados  
**Cuando** el sistema propone una acción  
**Entonces** mantiene la aprobación humana exigida  
**Y** la consolidación no habilita envíos, scraping o decisiones irreversibles.

### AC-019-024 — Escaneo de repositorio

**Dado** el commit candidato  
**Cuando** se ejecuta el escáner de secretos, PII y artefactos prohibidos  
**Entonces** no encuentra claves reales, tokens, bases, cachés, logs ni documentos
personales no ficticios.

## Verificación final requerida antes de cierre

### AC-019-025 — Evidencia completa

La spec solo podrá marcarse verificada cuando existan evidencias reproducibles de:

- búsqueda automatizada y allowlist de referencias heredadas;
- pruebas de prioridad y aliases de configuración;
- los cinco escenarios de SQLite y la reversión;
- regresión completa del ATS;
- regresión de PDF, OCR, ranking, embeddings, cachés y RAG;
- RBAC, privacidad, Alembic y escáner del repositorio;
- smoke de FastAPI y Streamlit;
- verificación visual de identidad TalentIA únicamente;
- ausencia de cambios no relacionados de la rama paralela.

Sin esas evidencias, `verification.md` no podrá declarar la funcionalidad cerrada.
