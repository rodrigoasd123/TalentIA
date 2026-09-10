# MASTER_IMPLEMENTATION_PLAN.md
# TalentIA — Enterprise Applicant Tracking & Talent Intelligence Platform

**Estado:** Plan maestro de implementación  
**Ámbito inicial:** TCS Perú  
**Objetivo:** Sustituir el manejo actual basado en Excel y demostrar que una solución interna puede cubrir las capacidades necesarias de un ATS empresarial, reduciendo trabajo manual, duplicados y tiempo hasta encontrar candidatos calificados.

---

## 1. Visión del producto

TalentIA será una **plataforma empresarial de Applicant Tracking + Talent Intelligence**.

No será solamente un CRUD de candidatos ni un buscador de palabras clave.

Debe convertirse en la **fuente única de verdad** para el proceso de reclutamiento de TCS Perú y conservar la memoria histórica necesaria para:

- administrar requisiciones;
- administrar candidatos;
- mantener Candidate 360;
- registrar cada participación del candidato en procesos diferentes;
- conservar historial de estados, entrevistas, evaluaciones y resultados;
- detectar duplicados;
- evitar doble contacto;
- importar listas provenientes de proveedores;
- controlar candidatos enviados por Adecco u otros proveedores;
- analizar CV;
- distinguir profundidad, recencia y contexto de skills;
- realizar matching explicable candidato-vacante;
- realizar Talent Rediscovery;
- administrar Talent Pools;
- medir el funnel de reclutamiento;
- generar métricas para demostrar el business case;
- proporcionar trazabilidad y auditoría empresarial.

La IA será una **herramienta de asistencia**. No tomará decisiones finales de contratación ni rechazo.

---

# 2. Principios obligatorios

Todo código generado para TalentIA debe respetar los siguientes principios:

1. Security by Design.
2. Privacy by Design.
3. Least Privilege.
4. Defense in Depth.
5. Human in the Loop para decisiones de selección.
6. Explainable AI.
7. Auditability.
8. Separation of Concerns.
9. Domain-oriented modular architecture.
10. API-first / contract-first.
11. Configuration over hardcoding.
12. Database migrations obligatorias.
13. No secretos en código.
14. No PII en logs técnicos.
15. Idempotencia para operaciones críticas.
16. Observabilidad desde el inicio.
17. Automated testing como requisito de entrega.
18. Backward-compatible APIs cuando sea posible.
19. No scraping de LinkedIn.
20. No automatización no autorizada de LinkedIn.
21. No dependencia directa del dominio con proveedores externos.
22. No usar el LLM como fuente de verdad.
23. No usar IA para inferir o evaluar atributos protegidos o sensibles.
24. No rechazo automático basado únicamente en un modelo.
25. Ningún módulo puede saltarse la capa de autorización.

---

# 3. Alcance

## 3.1 Incluido

- TCS Perú.
- IT Admin.
- HR Manager.
- Recruiters.
- Clientes.
- RGS / requisiciones.
- Job profiles.
- Requisitos must-have y nice-to-have.
- Candidate 360.
- CV PDF y DOCX.
- Experiencias.
- Educación.
- Certificaciones.
- Idiomas.
- Skills.
- Applications.
- Pipeline de reclutamiento.
- Historial completo.
- Entrevistas.
- Evaluaciones.
- Motivos de rechazo.
- Ofertas / cierre del proceso a nivel ATS.
- Talent Pools.
- Recontact Policies.
- Deduplicación.
- Merge de duplicados.
- Importación XLSX/CSV.
- Adecco / proveedores como fuente de candidatos.
- Provider Clearance.
- Career Skill Intelligence.
- Explainable Matching.
- Talent Rediscovery.
- Analytics.
- Auditoría.
- Notificaciones internas.
- SSO/OIDC-ready.
- Integración futura oficial con LinkedIn mediante interfaces desacopladas.

## 3.2 Fuera del MVP

- Portal del candidato.
- Portal de Adecco.
- Onboarding laboral posterior a contratación.
- Nómina.
- Scraping de LinkedIn.
- Automatización de navegadores contra LinkedIn.
- Búsqueda en GitHub.
- Envío automático de InMail.
- Integración RSC sin aprobación oficial.
- Decisiones autónomas de contratación.
- Rechazo automático por IA.
- Microservicios distribuidos.
- Kafka salvo justificación posterior.
- Multitenancy completo.
- Colombia en MVP.

---

# 4. Roles y autorización

## IT_ADMIN

Responsabilidades:

- alta/baja de cuentas cuando no exista provisioning corporativo;
- asignación de roles;
- configuración técnica;
- parámetros de integración;
- monitoreo operacional;
- configuración de seguridad autorizada.

Restricción:

Ser IT_ADMIN no implica acceso automático al contenido completo de candidatos, CV, notas de entrevistas o evaluaciones.

## HR_MANAGER

Representa a la jefa de Recursos Humanos.

Puede:

- visualizar operación global de RR. HH.;
- crear/aprobar requisiciones;
- configurar pipelines;
- configurar motivos;
- configurar políticas de recontacto;
- reasignar recruiter;
- revisar shortlists;
- resolver conflictos;
- realizar overrides justificados;
- consultar analytics;
- administrar configuración funcional.

## RECRUITER

Puede:

- registrar candidatos;
- importar candidatos;
- gestionar sus procesos;
- cargar CV;
- modificar estados permitidos;
- registrar interacciones;
- programar/registrar entrevistas;
- ejecutar matching;
- ejecutar rediscovery;
- revisar duplicados;
- crear shortlists;
- visualizar historial permitido.

## FUTURO: AUDITOR

Read-only sobre auditoría y reportes autorizados.

---

# 5. Modelo conceptual principal

La regla más importante es:

```text
Candidate != Application
```

Un candidato existe una sola vez, pero puede participar en múltiples procesos.

```text
Client
  |
  +---- Requisition
           |
           +---- Application ---- Candidate
                                   |
                                   +---- CandidateDocument
                                   +---- CandidateExperience
                                   +---- CandidateSkill
                                   +---- Education
                                   +---- Certification
                                   +---- Interaction
                                   +---- TalentPoolMembership
```

Ejemplo:

```text
Carlos Pérez
|
+-- Application 2025
|      Client: BBVA
|      Position: Java Developer
|      Result: REJECTED
|
+-- Application 2026
|      Client: BCP
|      Position: Backend Developer
|      Result: INTERVIEW
|
+-- Application 2026
       Client: BBVA
       Position: Java Senior
       Result: SOURCED
```

Nunca duplicar Candidate para representar una nueva postulación.

---

# 6. Arquitectura objetivo

## 6.1 Estrategia

Usar **Modular Monolith**.

No comenzar con microservicios.

Razones:

- menor complejidad operativa;
- transacciones simples;
- despliegue sencillo;
- desarrollo rápido para el piloto;
- límites de dominio definidos;
- posibilidad de extraer módulos posteriormente.

## 6.2 Arquitectura lógica

```text
                              Streamlit
                                  |
                                  v
                         REST API / OpenAPI
                                  |
              +-------------------+------------------+
              |                                      |
              v                                      v
        Application Layer                       Security Layer
              |
              v
        Domain Modules
              |
              +-----------------------------------------------+
              | identity/access                               |
              | clients                                       |
              | requisitions                                  |
              | candidates                                    |
              | applications                                  |
              | recruitment-workflow                          |
              | documents                                     |
              | duplicate-detection                           |
              | career-intelligence                           |
              | matching                                      |
              | rediscovery                                   |
              | talent-pools                                  |
              | providers                                     |
              | notifications                                 |
              | analytics                                     |
              | audit                                         |
              +-----------------------------------------------+
                                  |
                                  v
                      Infrastructure Adapters
                                  |
                +-----------------+-----------------+
                |                 |                 |
          SQLite local       Object Store       LLMProvider port
```

---

# 7. Stack objetivo

La restricción aprobada para el piloto es una solución Python. Cualquier cambio
de stack requiere una nueva decisión explícita.

## Backend

- Python 3.12+.
- FastAPI y Pydantic 2.
- SQLAlchemy 2 y Alembic.
- pytest, Ruff y MyPy.
- LangGraph únicamente para componentes catalogados como AI Agent.
- Los servicios deterministas permanecen como Python/domain services.

## Frontend

- Streamlit como cliente HTTP de FastAPI.
- La UI no escribe directamente en la base ni ejecuta reglas de negocio.

## Datos

- SQLite como fuente de verdad del piloto local.
- diseño SQLAlchemy portable, sin declarar compatibilidad con otro motor hasta probarla;
- almacenamiento de objetos S3-compatible mediante abstracción;
- Redis únicamente si aparece una necesidad demostrable;
- pgvector podrá evaluarse posteriormente, no es requisito de la primera fase.

## Plataforma

- Docker.
- Docker Compose para desarrollo.
- configuración 12-factor.
- despliegue OCI/cloud-agnostic.
- GitHub Actions inicialmente, adaptable a CI/CD corporativo.

## Observabilidad

- OpenTelemetry.
- structured logging.
- health/readiness endpoints.
- métricas.
- correlation/trace ID.
- MLflow Tracing para toda ejecución de LangGraph, con sanitización de PII y
  degradación controlada si MLflow no está disponible.

## 7.1 Restricción permanente para agentes de IA

Todo componente catalogado como `AI Agent` debe ser un grafo LangGraph con
estado tipado, nodos de responsabilidad única, rutas condicionales, schemas
Pydantic, tools/skills explícitos, guards, límites de pasos, timeout, retries y
Human-in-the-Loop/checkpointing cuando corresponda. Los prompts son externos,
versionados y poseen ID.

Los grafos dependen de `LLMProvider`, nunca de Gemini directamente. El primer
adaptador será `GeminiProvider` mediante la integración Python mantenida; las
variables son `LLM_PROVIDER=gemini`, `GEMINI_MODEL` y `GEMINI_API_KEY`, sin
secretos en Git. Gemini Free Tier solo puede recibir datos sintéticos y el envío
de CV o PII real queda deshabilitado hasta aprobación de Security/Legal.

La inicialización de MLflow/LangGraph se centraliza. Cada ejecución registra
`agent_execution_id`, `thread_id` cuando aplique, versiones de agente, grafo y
prompt, modelo, latencia, estado/error y metadatos de evaluación. Los traces
usan IDs o referencias internas y redactan CV, documento, email, teléfono y
demás PII. La caída de Gemini o MLflow no bloquea el core ATS ni corrompe sus
transacciones.

---

# 8. Estructura del repositorio

Estructura vigente para el stack Python:

```text
app/
  domain/
  application/
  infrastructure/
  api/
  agents/
    shared/
      state/
      tools/
      guards/
      tracing/
      prompts/
    requirement_intelligence/
    cv_intelligence/
    career_intelligence/
    matching/
    rediscovery/
ats_frontend/
migrations/
tests/
docs/
```

Cada directorio de agente contiene `graph.py`, `state.py`, `nodes.py`,
`schemas.py`, `tools.py`, `guards.py`, `config.py`, `prompts/` y `tests/`. La
estructura Java/React siguiente se conserva solo como referencia histórica y
queda sustituida por la estructura Python anterior:

```text
talentia/
|
+-- backend/
|   +-- src/main/java/.../
|   |   +-- shared/
|   |   +-- identity/
|   |   +-- access/
|   |   +-- clients/
|   |   +-- requisitions/
|   |   +-- candidates/
|   |   +-- applications/
|   |   +-- workflow/
|   |   +-- documents/
|   |   +-- duplicates/
|   |   +-- careerintelligence/
|   |   +-- matching/
|   |   +-- rediscovery/
|   |   +-- talentpools/
|   |   +-- providers/
|   |   +-- notifications/
|   |   +-- analytics/
|   |   +-- audit/
|   |
|   +-- src/test/
|
+-- frontend/
|   +-- src/
|       +-- app/
|       +-- modules/
|       +-- shared/
|       +-- api/
|       +-- components/
|       +-- auth/
|
+-- infrastructure/
|   +-- docker/
|   +-- observability/
|
+-- docs/
|   +-- architecture/
|   +-- api/
|   +-- adr/
|   +-- security/
|   +-- runbooks/
|
+-- scripts/
|
+-- .github/workflows/
|
+-- docker-compose.yml
+-- README.md
```

No organizar el backend únicamente como:

```text
controller/
service/
repository/
entity/
```

Los módulos deben representar capacidades del negocio.

---

# 9. Módulos

## 9.1 Identity / Access

Debe proporcionar:

- integración OIDC;
- proveedor local únicamente para development/test;
- roles;
- permissions;
- scopes;
- estado de usuario;
- session/security events;
- autorización method-level.

Preparar:

```text
IdentityProviderPort
  +-- LocalIdentityAdapter
  +-- CorporateOidcAdapter
```

---

## 9.2 Clients

Representa los clientes de las requisiciones.

Campos mínimos:

```text
id
code
name
status
createdAt
updatedAt
```

Nunca hardcodear BBVA u otro cliente.

---

## 9.3 Requisitions

Representa RGS / requisiciones.

Debe soportar:

- cliente;
- cargo;
- descripción;
- número de posiciones;
- ubicación;
- modalidad;
- seniority;
- skills obligatorias;
- skills deseables;
- experiencia mínima;
- industria deseable;
- estado;
- recruiter owner;
- fechas;
- versión del requisito.

Estados iniciales:

```text
DRAFT
PENDING_APPROVAL
OPEN
ON_HOLD
CLOSED
CANCELLED
```

La configuración futura puede ampliar el workflow.

---

# 10. Requirement Intelligence

La IA debe convertir RGS/JD a un objeto estructurado.

Ejemplo:

Input:

```text
Necesitamos un Java Backend para BBVA,
3 años de Java, Spring Boot, microservicios,
SQL y deseable Kafka.
```

Output validado:

```json
{
  "title": "Java Backend Developer",
  "seniority": "MID",
  "mustHave": [
    {"skill": "Java", "minimumMonths": 36},
    {"skill": "Spring Boot"},
    {"skill": "Microservices"},
    {"skill": "SQL"}
  ],
  "niceToHave": [
    {"skill": "Kafka"}
  ]
}
```

Reglas:

- la IA propone;
- Recruiter/HR Manager confirma;
- guardar versión;
- guardar autor;
- no sobrescribir silenciosamente criterios aprobados;
- si el RGS es ambiguo, marcar `NEEDS_REVIEW`.

---

# 11. Candidate 360

Debe existir un identificador interno estable.

Ejemplo:

```text
candidateId: UUID
candidateNumber: CAN-00000183
```

Candidate 360 debe reunir:

```text
Identity
Contact information
CV/Documents
Experience
Education
Certifications
Languages
Skills
Applications
Interactions
Evaluations
Match history
Sources
Talent pools
Recontact status
Audit history
```

Candidate no debe almacenar "estado de selección" global.

El estado pertenece a Application.

---

# 12. Application

Entidad que une Candidate con Requisition.

Debe permitir múltiples aplicaciones por candidato.

Campos conceptuales:

```text
id
candidateId
requisitionId
source
providerId
ownerRecruiterId
currentStage
status
createdAt
closedAt
closureReasonId
```

---

# 13. Recruitment Workflow

El pipeline no debe quedar hardcodeado.

Proporcionar configuración funcional:

```text
SOURCED
CONTACTED
SCREENING
CV_RECEIVED
PRESELECTED
INTERVIEW_HR
INTERVIEW_TECH
FINAL_REVIEW
OFFER
HIRED
```

Estados terminales posibles:

```text
REJECTED
WITHDRAWN
NOT_INTERESTED
UNREACHABLE
HIRED
CANCELLED
```

Cada transición debe generar:

```text
ApplicationStageHistory
```

con:

```text
fromStage
toStage
changedBy
changedAt
reason
comment
```

Nunca editar retrospectivamente el historial.

---

# 14. Rejection Reasons

No usar free text como único mecanismo.

Crear catálogo configurable:

```text
SKILL_GAP
SENIORITY_GAP
COMPENSATION
AVAILABILITY
LOCATION
NOT_INTERESTED
WITHDRAWN
CLIENT_REJECTION
OTHER
```

`OTHER` obliga a ingresar comentario.

Los motivos deben ser configurables por HR Manager.

---

# 15. Recontact Policy Engine

No hardcodear períodos de recontacto.

Modelo:

```text
RejectionReason
       |
       v
RecontactPolicy
```

Tipos:

```text
ALWAYS_ALLOWED
WAITING_PERIOD
MANUAL_REVIEW
NOT_ALLOWED
```

El período, cuando exista, será configuración de RR. HH.

Salida:

```text
ELIGIBLE
NOT_YET_ELIGIBLE
MANUAL_REVIEW
NOT_ELIGIBLE
```

La política debe permitir excepciones justificadas por HR Manager.

---

# 16. Document Management

Formatos MVP:

- PDF;
- DOCX.

Flujo:

```text
Upload
  |
  v
MIME validation
  |
  v
size validation
  |
  v
malware scanning hook
  |
  v
object storage
  |
  v
metadata DB
  |
  v
async text extraction
```

Nunca guardar el archivo binario completo directamente en una entidad JPA.

Registrar:

```text
documentId
candidateId
type
originalFileName
mimeType
size
checksum
storageKey
uploadedBy
uploadedAt
status
```

El nombre original nunca debe usarse directamente como ruta física.

---

# 17. CV Parsing

Pipeline:

```text
CV
 |
 v
Text Extraction
 |
 v
Normalization
 |
 v
Structured AI Extraction
 |
 v
Schema Validation
 |
 v
Human Review when needed
 |
 v
Candidate Profile
```

Extraer:

```text
experiences[]
education[]
skills[]
certifications[]
languages[]
summary
```

La salida del LLM debe utilizar JSON Schema o respuesta estructurada equivalente.

No insertar directamente una respuesta no validada del LLM en tablas productivas.

---

# 18. Career Skill Intelligence

Es uno de los diferenciadores del producto.

No evaluar:

```text
candidate.skills.contains("Java")
```

Debe generar un Skill Profile contextual.

Ejemplo:

```text
Java
  totalExperienceMonths: 6
  firstUsed: 2021
  lastUsed: 2021
  maxSeniority: INTERN
  current: false

PHP
  totalExperienceMonths: 60
  firstUsed: 2021
  lastUsed: 2026
  maxSeniority: SENIOR
  current: true
```

Para cada skill registrar evidencia:

```text
CandidateExperience
Skill
Evidence
Confidence
```

Variables del análisis:

- duración;
- recencia;
- seniority;
- rol;
- frecuencia;
- responsabilidades;
- evidencia explícita;
- uso actual;
- experiencia profesional vs educativa/personal.

No confundir conocimiento declarado con experiencia profesional.

---

# 19. Skill Taxonomy

Crear catálogo normalizado.

Ejemplos:

```text
Spring
Spring Framework
Spring Boot
```

pueden pertenecer a relaciones distintas.

La taxonomía debe soportar:

```text
canonicalSkill
aliases[]
relatedSkills[]
category
```

No usar solamente comparación exacta de strings.

---

# 20. Duplicate Detection

Debe ser híbrido.

## Nivel 1 — Exact match

Señales fuertes:

```text
document
email
phone
LinkedIn URL, cuando haya sido proporcionada legítimamente
```

## Nivel 2 — Normalized match

```text
normalized name
normalized phone
normalized email
```

## Nivel 3 — Probabilistic/Fuzzy

Considerar únicamente datos autorizados:

```text
name similarity
email similarity
phone
employment overlap
location
other non-sensitive identifiers
```

Resultado:

```text
NO_MATCH
POSSIBLE_DUPLICATE
HIGH_CONFIDENCE_DUPLICATE
EXACT_DUPLICATE
```

Nunca hacer merge automático de casos fuzzy.

Crear:

```text
DuplicateCase
```

con:

```text
candidateA
candidateB
score
signals
status
reviewedBy
resolution
```

---

# 21. Merge de candidatos

El merge debe ser transaccional y auditable.

Nunca:

```text
DELETE duplicate
```

sin conservar trazabilidad.

Guardar:

```text
CandidateMergeEvent
survivorCandidateId
mergedCandidateId
performedBy
timestamp
fieldDecisions
```

Todas las Applications del candidato absorbido deben conservarse.

---

# 22. Importación XLSX/CSV

No insertar archivos directamente a producción.

Pipeline:

```text
Upload
 |
 v
Import Batch
 |
 v
Staging
 |
 v
Schema validation
 |
 v
Normalization
 |
 v
Duplicate detection
 |
 v
Business validation
 |
 v
Preview
 |
 v
Human confirmation
 |
 v
Commit
```

Estados:

```text
UPLOADED
VALIDATING
READY_FOR_REVIEW
PARTIALLY_VALID
REJECTED
IMPORTED
```

Mostrar:

```text
total rows
new
duplicates
possible duplicates
already in process
recontactable
invalid
```

Guardar errores por fila.

La importación debe ser idempotente usando checksum/batch identifier.

---

# 23. Provider Management

MVP:

Adecco no tendrá acceso directo.

Crear:

```text
Provider
ProviderSubmissionBatch
ProviderSubmission
ProviderPerformance
```

Provider Clearance debe devolver internamente:

```text
NEW
EXISTING
ALREADY_IN_PROCESS
RECONTACTABLE
DO_NOT_SUBMIT
MANUAL_REVIEW
INVALID
```

Un reporte externo nunca debe exponer:

- evaluaciones internas;
- comentarios privados;
- notas de entrevista;
- scoring detallado;
- PII innecesaria.

---

# 24. Explainable Matching

No delegar todo el matching a un LLM.

Arquitectura:

```text
            Matching Engine
                  |
      +-----------+-----------+
      |           |           |
      v           v           v
Deterministic   Career      Semantic
  Rules       Intelligence  Similarity
      \           |           /
       +----------+----------+
                  |
                  v
          Explainable Result
```

Evaluar únicamente criterios relacionados con el puesto.

Ejemplo:

```text
Java >= 3 years
Required
Candidate: 4.1 years
Result: MATCH
Evidence: Experiences #2 and #3

Spring Boot
Required
Candidate: 3 years
Result: MATCH

Kafka
Nice-to-have
Candidate: insufficient evidence
Result: GAP
```

Resultado:

```text
overallScore
mustHaveScore
niceToHaveScore
experienceScore
recencyScore
evidence[]
gaps[]
warnings[]
recommendation
```

La recomendación es informativa.

No generar automáticamente:

```text
REJECT CANDIDATE
```

---

# 25. AI Governance

Crear abstracción:

```text
LLMProvider
```

Adaptador inicial:

```text
LLMProvider
  +-- GeminiProvider
```

Adaptadores futuros:

```text
AzureOpenAIAdapter
OpenAIAdapter
InternalModelAdapter
OtherApprovedProviderAdapter
```

El dominio no conocerá SDKs específicos.

Cada ejecución IA deberá registrar:

```text
executionId
useCase
provider
model
promptTemplateVersion
schemaVersion
timestamp
latency
token/cost metadata when available
status
inputReference
outputReference
humanReviewStatus
```

No guardar PII completa en logs de aplicación.

Los prompts deben versionarse en el repositorio.

No se permiten llamadas al LLM desde routers, servicios dispersos o páginas
Streamlit. El flujo autorizado es:

```text
LangGraph -> resultado Pydantic validado -> application service
          -> validación de negocio -> transacción -> persistencia
```

Agentes previstos, sin mega-agent general:

```text
RequirementIntelligenceAgent
CVIntelligenceAgent
CareerIntelligenceAgent
MatchingAgent
RediscoveryAgent
```

RBAC, workflow, auditoría, transacciones, validación de archivos, políticas de
recontacto, scoring determinista y duplicados exactos no son agentes. Una futura
ayuda IA para duplicados ambiguos no sustituirá el motor determinista.

---

# 26. AI Evaluation

Antes de producción, crear dataset de evaluación anonimizado/sintético.

Medir por caso:

## CV parsing

- field accuracy;
- experience extraction accuracy;
- skill extraction precision/recall.

## Matching

- precision@K;
- recruiter agreement;
- false-positive rate;
- false-negative review sample;
- explanation correctness.

## Deduplication

- precision;
- recall;
- false merge rate.

El deployment de cambios de modelo/prompt requiere superar quality gate.

Cada agente requiere pruebas unitarias de nodos, routing/grafo y evaluación del
output estructurado. La suite debe demostrar redacción de PII en traces y el
fallback cuando Gemini o MLflow no estén disponibles.

---

# 27. Talent Rediscovery

Cuando se crea/activa una requisición:

```text
Requisition
   |
   v
Internal Candidate Search
   |
   v
Recontact Eligibility
   |
   v
Career Intelligence
   |
   v
Matching
   |
   v
Rediscovery Results
```

Priorizar candidatos históricos según:

- requisitos actuales;
- skills relevantes;
- recencia;
- seniority;
- experiencia;
- outcome histórico;
- política de recontacto;
- proceso actualmente activo;
- consentimiento/base legal aplicable.

Mostrar contexto:

```text
Previous applications
Previous stages
Previous rejection reason
Last contact
Recontact eligibility
Current match
```

No considerar un rechazo histórico como prohibición permanente salvo política explícita.

---

# 28. Talent Pools

Permitir pools manuales y dinámicos.

Ejemplos:

```text
Java
COBOL/Mainframe
Data
QA
Cloud
Java + Banking
COBOL + CICS
```

Dynamic Talent Pool:

```text
criteria
lastRefresh
candidateCount
```

---

# 29. Search

Primera etapa:

- PostgreSQL indexes;
- full-text search;
- structured filters.

Filtros:

```text
skills
experience
seniority
client history
application history
source
availability/contactability
last contact
talent pool
```

La búsqueda semántica debe implementarse solo después de medir necesidad.

---

# 30. Analytics

KPIs mínimos:

```text
Time to first qualified CV
Qualified CV / received CV
Duplicate rate
Duplicates prevented
Provider useful-CV ratio
Time in stage
Requisition aging
Source effectiveness
Rediscovered candidates
Rediscovery conversion
Applications per requisition
Interview conversion
Hire conversion
Human effort estimate
Incidents/errors
```

Todos los indicadores deben tener definición formal.

Ejemplo:

```text
qualified_cv_rate =
qualified_cv_count / received_cv_count
```

No mostrar un KPI si su definición o fuente no está definida.

---

# 31. Auditoría

Todo evento crítico debe generar AuditEvent.

Ejemplos:

```text
USER_ROLE_CHANGED
CANDIDATE_CREATED
CANDIDATE_UPDATED
CV_DOWNLOADED
APPLICATION_CREATED
APPLICATION_STAGE_CHANGED
REJECTION_RECORDED
REQUISITION_APPROVED
MATCH_EXECUTED
MATCH_REVIEWED
DUPLICATE_MERGED
IMPORT_CONFIRMED
POLICY_CHANGED
```

Campos:

```text
eventId
timestamp
actorId
action
resourceType
resourceId
correlationId
metadata
```

La auditoría debe ser append-only desde la aplicación.

---

# 32. Seguridad

## Autenticación

Producción:

```text
Corporate Identity Provider
          |
          v
       OIDC
          |
          v
      TalentIA
```

Development:

Local provider aislado.

Nunca habilitar usuarios locales de desarrollo en producción.

## Autorización

RBAC + resource/data scope.

Preparar scopes:

```text
OWN
TEAM
ALL
```

## Sesiones/tokens

- expiración;
- issuer validation;
- audience validation;
- secure cookies cuando aplique;
- no tokens en localStorage si se adopta BFF/session architecture;
- CSRF protection cuando corresponda.

## Web

- CSP.
- HSTS.
- X-Content-Type-Options.
- Referrer-Policy.
- frame protection.
- CORS allowlist.

## API

- validation.
- authorization en servidor.
- rate limiting para endpoints sensibles.
- request size limits.
- pagination limits.
- idempotency keys en operaciones apropiadas.

## Archivos

- MIME whitelist.
- extensión no es suficiente.
- tamaño máximo.
- checksum.
- malware scanning integration point.
- object storage privado.
- URLs firmadas y temporales.
- autorización antes de descarga.

---

# 33. PII / privacidad

Tratar como sensible:

```text
document number
email
phone
CV
address
interview notes
evaluations
candidate history
```

Reglas:

- cifrado en tránsito TLS;
- cifrado de almacenamiento;
- no PII en logs;
- no PII en exception messages;
- secrets en secret manager;
- acceso por mínimo privilegio;
- retención configurable;
- trazabilidad de acceso;
- export/delete/anonymization preparados para políticas aplicables.

No enviar CV/PII a un proveedor LLM externo hasta que Seguridad/Legal confirme que está permitido.

---

# 34. Datos que NO deben participar en IA de matching

TalentIA no debe utilizar para scoring o ranking:

- sexo/género;
- edad salvo requisito legal expresamente validado;
- raza/etnia;
- religión;
- discapacidad;
- orientación sexual;
- estado civil;
- fotografía;
- afiliación política;
- información médica;
- antecedentes u otros datos sensibles no relacionados legítimamente con el matching técnico;
- proxies diseñados para inferir atributos protegidos.

Los filtros de cumplimiento/antecedentes que el negocio pueda necesitar pertenecen a procesos separados y requieren validación de Legal/Compliance.

---

# 35. Persistencia

Usar UUID como PK técnica.

Agregar `created_at`, `updated_at`, versionado optimista donde corresponda.

No usar:

```text
spring.jpa.hibernate.ddl-auto=update
```

en producción.

Flyway es la única fuente de evolución de schema.

---

# 36. Concurrency

Entidades críticas deben usar optimistic locking:

```text
@Version
```

Ejemplos:

- Application.
- Requisition.
- Candidate cuando existe edición concurrente.
- policy/configuration.

Responder con `409 Conflict` en conflictos controlados.

---

# 37. Transactions

Definir boundaries explícitos.

Ejemplos transaccionales:

```text
Create Application
Change Application Stage
Merge Candidates
Confirm Import Batch
Approve Requisition
```

No envolver llamadas lentas al LLM dentro de una transacción DB.

---

# 38. Async Processing

CV parsing, matching masivo, rediscovery e importaciones grandes deben ser asíncronos.

Crear:

```text
Job
JobExecution
```

y abstracción:

```text
TaskQueuePort
```

MVP puede usar PostgreSQL como job queue segura.

Preparar adapter futuro para broker.

Usar Outbox Pattern para eventos que requieren entrega confiable.

---

# 39. API Design

Base:

```text
/api/v1
```

Ejemplos:

```text
POST   /api/v1/requisitions
GET    /api/v1/requisitions
GET    /api/v1/requisitions/{id}
POST   /api/v1/requisitions/{id}/approve

POST   /api/v1/candidates
GET    /api/v1/candidates/{id}
GET    /api/v1/candidates/{id}/timeline
POST   /api/v1/candidates/{id}/documents

POST   /api/v1/applications
POST   /api/v1/applications/{id}/transitions

POST   /api/v1/imports/provider
GET    /api/v1/imports/{id}
POST   /api/v1/imports/{id}/confirm

GET    /api/v1/duplicates
POST   /api/v1/duplicates/{id}/resolve

POST   /api/v1/requisitions/{id}/matches
POST   /api/v1/requisitions/{id}/rediscovery

GET    /api/v1/analytics/funnel
GET    /api/v1/analytics/providers
```

OpenAPI es parte del build.

---

# 40. Error Contract

Formato consistente:

```json
{
  "type": "https://talentia/errors/validation",
  "title": "Validation error",
  "status": 400,
  "code": "VALIDATION_ERROR",
  "correlationId": "...",
  "errors": []
}
```

No devolver stack traces.

---

# 41. Frontend

Pantallas MVP:

```text
Login
Dashboard
Requisitions
Requisition Detail
Candidates
Candidate 360
Applications
Pipeline
CV/Documents
Duplicate Review
Provider Imports
Matching
Rediscovery
Talent Pools
Analytics
Configuration
Audit
```

El frontend nunca debe determinar permisos como única medida.

Backend es autoridad final.

---

# 42. UX empresarial

Requisitos:

- loading state;
- empty state;
- error state;
- permission denied state;
- confirmation para acciones destructivas;
- autosave solo cuando sea seguro;
- accesibilidad;
- teclado;
- paginación;
- filtros persistibles;
- export controlado;
- timestamps y zona horaria consistentes.

---

# 43. Observabilidad

Cada request:

```text
traceId
correlationId
actorId when available
endpoint
status
duration
```

Nunca loggear bodies completos con PII.

Métricas:

```text
HTTP latency
HTTP error rate
DB latency
AI latency
AI failures
document processing failures
import failures
job queue depth
job execution duration
```

Para agentes LangGraph, MLflow Tracing cubre ejecución de grafo, nodos, tools,
llamadas LLM, latencia, modelo, versiones de prompt/grafo, estado, errores y
evaluación. La integración LangChain/LangGraph se activa centralmente y aplica
redacción antes de exportar; nunca se almacenan CV completos ni PII en traces.

---

# 44. SLO inicial

Objetivos de ingeniería para piloto:

```text
Availability: >= 99.5% durante horario operativo
p95 API read: < 500 ms sin IA
p95 API write: < 800 ms sin IA
AI operations: async cuando > 2 s
zero known critical security vulnerabilities
zero unaudited privilege changes
```

Ajustar SLO productivo con infraestructura corporativa.

---

# 45. Backup / Recovery

Antes de producción debe existir:

- backup automático;
- point-in-time recovery cuando infraestructura lo permita;
- backup del object storage;
- restore test;
- runbook.

Objetivo inicial a validar con negocio:

```text
RPO <= 24 h
RTO <= 4 h
```

No declarar estos valores como SLA contractual hasta aprobación.

---

# 46. Testing Strategy

## Unit

Domain rules.

Especial prioridad:

- recontact policies;
- stage transitions;
- duplicate rules;
- scoring;
- permissions;
- normalization.

## Integration

Usar Testcontainers para PostgreSQL.

Probar:

- repositories;
- migrations;
- transaction boundaries;
- security;
- REST APIs.

## Contract

Validar OpenAPI.

## E2E

Playwright.

Flujos mínimos:

```text
create requisition
approve requisition
create candidate
upload CV
parse CV
create application
run match
change stages
rediscover candidate
import provider file
detect duplicate
resolve duplicate
```

## Security

- SAST;
- dependency scanning;
- secrets scanning;
- container scanning;
- OWASP-oriented tests.

## Performance

k6/Gatling para:

- candidate search;
- dashboard;
- provider imports;
- rediscovery batches.

---

# 47. Quality Gates

No mergear PR si falla:

```text
compile
lint
unit tests
integration tests
OpenAPI validation
migration validation
SAST
dependency vulnerability policy
secret scan
container scan when applicable
```

Código crítico sin tests no se considera terminado.

---

# 48. CI/CD

Pipeline:

```text
PR
 |
 v
Compile
 |
 v
Lint
 |
 v
Unit tests
 |
 v
Integration tests
 |
 v
Security scans
 |
 v
Build containers
 |
 v
Deploy DEV
 |
 v
Smoke tests
 |
 v
Approval
 |
 v
STAGING
 |
 v
E2E
 |
 v
Approval
 |
 v
PROD
```

No desplegar directamente desde laptop.

---

# 49. Environments

```text
local
dev
staging
prod
```

Cada entorno:

- DB independiente;
- secrets independientes;
- storage independiente;
- identity configuration independiente.

Nunca copiar automáticamente producción hacia development.

---

# 50. ADR

Toda decisión arquitectónica relevante debe documentarse.

Primeros ADR:

```text
ADR-001 Modular Monolith
ADR-002 PostgreSQL
ADR-003 OIDC Authentication
ADR-004 Object Storage for CV
ADR-005 Human-in-the-loop AI
ADR-006 Explainable Hybrid Matching
ADR-007 Provider Import Staging
ADR-008 No LinkedIn Scraping
ADR-009 Async Jobs + Outbox
ADR-010 Audit Strategy
```

Las decisiones efectivamente aceptadas y numeradas en el repositorio prevalecen
sobre esta lista inicial. La arquitectura LangGraph + MLflow + proveedor Gemini
desacoplado queda registrada en `docs/adr/ADR-007-*`.

---

# 51. Fases de implementación

## FASE 0 — Auditoría y foundation

Objetivo:

Establecer base técnica confiable antes de funcionalidades.

Tareas:

- auditar repositorio actual;
- identificar stack;
- identificar código reutilizable;
- identificar deuda técnica;
- eliminar secretos;
- establecer branches;
- definir formatting/lint;
- Docker;
- PostgreSQL;
- Flyway;
- health checks;
- OpenAPI;
- error contract;
- logging;
- CI inicial;
- ADR iniciales.

Entrega:

```text
Application starts
DB migration succeeds
Health endpoint works
CI green
No critical secrets/security findings
```

No empezar módulos IA antes de cerrar Fase 0.

---

## FASE 1 — Security & Access Foundation

Implementar:

- users;
- roles;
- permissions;
- local auth para development;
- OIDC-ready architecture;
- Spring Security;
- backend authorization;
- audit de login/access changes.

Acceptance:

- recruiter no administra usuarios;
- HR Manager no modifica configuración técnica;
- IT Admin no obtiene acceso de negocio automáticamente;
- endpoint protegido falla correctamente;
- tests de autorización completos.

---

## FASE 2 — Clients + Requisitions

Implementar:

- Client;
- Requisition;
- requirements;
- skills requirements;
- owner recruiter;
- lifecycle;
- approval.

UI:

- listado;
- creación;
- detalle;
- aprobación;
- filtros.

Acceptance:

Una requisición puede quedar completamente definida sin IA.

---

## FASE 3 — Candidate 360

Implementar:

- Candidate;
- identity/contact;
- experience;
- education;
- certifications;
- skills;
- source;
- timeline base.

UI:

- candidate search;
- candidate detail;
- tabs Candidate 360.

Acceptance:

Un candidato existe una sola vez aunque participe en procesos diferentes.

---

## FASE 4 — Applications + Workflow

Implementar:

- Application;
- pipeline;
- transitions;
- history;
- rejection reasons;
- interviews;
- evaluations;
- ownership.

Acceptance:

Todo cambio de etapa queda auditado y es reconstruible.

---

## FASE 5 — Documents + CV Pipeline

Implementar:

- secure upload;
- object storage;
- checksum;
- metadata;
- text extraction PDF;
- text extraction DOCX;
- async processing;
- processing status.

Acceptance:

CV se almacena fuera de DB, acceso autorizado y procesamiento reproducible.

---

## FASE 6 — Importación del histórico

Implementar:

- XLSX;
- CSV;
- staging;
- mapping de columnas;
- validation;
- preview;
- import batch;
- error report;
- idempotency.

Objetivo:

Migrar Excel actual sin contaminar la base.

---

## FASE 7 — Duplicate Detection

Implementar:

- exact matching;
- normalization;
- fuzzy matching;
- DuplicateCase;
- review;
- merge;
- merge audit.

Acceptance:

Nunca merge automático por fuzzy score.

Métrica:

```text
duplicate_precision
duplicates_prevented
```

---

## FASE 8 — Provider Control

Implementar:

- Provider;
- Adecco source;
- submission batch;
- candidate clearance;
- provider analytics;
- exclusion output.

Acceptance:

Una lista de Adecco puede validarse antes de crear candidatos duplicados.

---

## FASE 9 — Requirement Intelligence

Implementar:

- foundation de agentes bajo `app/agents/shared/`;
- LangGraph y MLflow Tracing centralizados;
- `LLMProvider` y `GeminiProvider` desacoplados;
- sanitización/redacción de traces y guard de datos sintéticos/free tier;
- retry, timeout, maximum graph steps y validación estructurada;
- `RequirementIntelligenceAgent` con state, graph, nodes, schemas, tools,
  guards, config, prompts y tests;
- prompt registry;
- structured RGS extraction;
- schema validation;
- review flow;
- versioning.

Acceptance:

La IA nunca activa una requisición sin confirmación humana.

Gate adicional:

El agente no comienza hasta que sus prerrequisitos deterministas estén completos
y el core siga operando con Gemini y MLflow indisponibles.

---

## FASE 10 — CV Intelligence

Implementar:

- `CVIntelligenceAgent` con el contrato estructural común de LangGraph;
- structured CV extraction;
- evidence links;
- confidence;
- review flow;
- normalized skills;
- experience timeline.

Acceptance:

Toda skill inferida debe diferenciarse de evidencia explícita.

Gemini Free Tier solo se prueba con CV sintéticos; la salida validada no escribe
directamente en la base de datos.

---

## FASE 11 — Career Skill Intelligence

Implementar:

- `CareerIntelligenceAgent` con el contrato estructural común de LangGraph;
- experience-to-skill relation;
- total months;
- recency;
- seniority;
- current usage;
- professional/academic distinction;
- dominant skill calculation.

Caso obligatorio:

```text
Java 6 meses como practicante en 2021
PHP 5 años, senior, actual
```

El sistema NO debe considerar automáticamente al candidato como Java Senior.

---

## FASE 12 — Explainable Matching

Implementar:

- `MatchingAgent` con el contrato estructural común de LangGraph;
- deterministic requirements;
- career score;
- semantic support;
- weighted scoring;
- evidence;
- gaps;
- warnings;
- explanation;
- match version.

Acceptance:

Cada resultado puede responder:

```text
why matched?
why not matched?
which evidence?
which requirement is missing?
```

---

## FASE 13 — Recontact Policy

Implementar:

- configurable policies;
- waiting periods;
- manual review;
- exception;
- eligibility evaluation.

No inventar reglas específicas de TCS.

Configurarlas cuando RR. HH. las apruebe.

---

## FASE 14 — Talent Rediscovery

Implementar:

- `RediscoveryAgent` con el contrato estructural común de LangGraph;
- búsqueda histórica;
- recontact filter;
- active-process conflict;
- matching;
- shortlist;
- prior-process context.

Acceptance:

Al crear una requisición, recruiter puede identificar candidatos históricos relevantes antes de comenzar sourcing externo.

---

## FASE 15 — Talent Pools

Implementar:

- static pools;
- dynamic pools;
- criteria;
- refresh;
- membership history.

---

## FASE 16 — Analytics

Construir dashboards de:

- funnel;
- requisition aging;
- provider quality;
- duplicates;
- rediscovery;
- matching;
- sources;
- stage time.

Definir fórmulas antes de UI.

---

## FASE 17 — Hardening

Antes del piloto real:

- penetration/security review;
- dependency cleanup;
- query profiling;
- indexes;
- load tests;
- restore test;
- observability dashboards;
- alerting;
- runbooks;
- retention;
- access review;
- AI evaluation;
- privacy review.

---

## FASE 18 — Piloto TCS Perú

Scope:

- un cliente;
- una familia de perfil;
- recruiters seleccionados;
- dataset autorizado;
- comparación con proceso actual.

Medir:

```text
time_to_first_qualified_cv
qualified_cv_rate
duplicates_prevented
provider_duplicate_rate
rediscovered_candidates
hours_saved_estimate
recruiter_acceptance_of_matches
system_incidents
```

No medir éxito como "reemplazamos personas".

Medir reducción de esfuerzo, calidad y velocidad.

---

# 52. Orden de prioridades

## P0

Debe existir para poder operar:

```text
Security
Users/Roles
Clients
Requisitions
Candidates
Applications
Workflow
History
Documents
Audit
Excel/CSV Import
```

## P1

Diferenciación principal:

```text
Deduplication
Provider Clearance
CV Parsing
Career Skill Intelligence
Explainable Matching
Recontact Policies
Rediscovery
```

## P2

Madurez:

```text
Talent Pools
Analytics advanced
Notifications
AI assistant
bulk workflows
```

## P3

Integraciones futuras:

```text
Corporate OIDC production integration
LinkedIn official integration if approved
Teams/email integrations
future provider portal
```

---

# 53. Definition of Done

Una historia no está terminada solo porque "funciona".

Debe cumplir cuando corresponda:

```text
business rule implemented
authorization implemented
validation implemented
audit implemented
migration included
unit tests
integration tests
API documented
frontend states
error handling
logging
metrics
security review
no secrets
no high/critical vulnerabilities
code reviewed
acceptance criteria passed
```

---

# 54. Reglas específicas para Codex

Codex NO debe:

```text
- generar todo el proyecto en una sola iteración;
- cambiar arquitectura sin ADR;
- añadir dependencias sin justificar;
- usar microservicios por defecto;
- usar Kafka por defecto;
- inventar reglas de TCS;
- hardcodear clientes;
- hardcodear períodos de recontacto;
- generar porcentajes IA sin evidencia;
- permitir rechazo automático;
- hacer scraping de LinkedIn;
- incluir datos reales de candidatos en tests;
- loggear CV/PII;
- crear endpoints sin autorización;
- usar ddl-auto=update en producción;
- ejecutar migrations destructivas sin estrategia;
```

Codex SÍ debe:

```text
- trabajar fase por fase;
- analizar código antes de modificar;
- reutilizar código válido;
- crear ADR cuando cambie decisiones importantes;
- mantener tests;
- actualizar OpenAPI;
- actualizar migrations;
- mantener documentación;
- ejecutar tests antes de cerrar cada tarea;
- reportar riesgos y deuda técnica;
```

---

# 55. Protocolo de ejecución para Codex

Para cada fase:

```text
1. Inspect
2. Plan
3. Implement
4. Test
5. Security check
6. Document
7. Report
```

Antes de escribir código debe indicar:

```text
Files to modify
Files to create
Database changes
API changes
Security impact
Tests to add
Risks
```

Después debe indicar:

```text
Implemented
Tests executed
Tests passed
Known limitations
Next recommended task
```

---

# 56. Primer prompt para Codex

Usar después de colocar este documento en el repositorio:

```text
Read MASTER_IMPLEMENTATION_PLAN.md completely.

Do not implement business features yet.

Perform PHASE 0 only.

First inspect the entire current repository and produce:

1. current architecture;
2. current backend/frontend stack;
3. reusable components;
4. technical debt;
5. security findings;
6. missing project foundation;
7. differences between the repository and MASTER_IMPLEMENTATION_PLAN.md;
8. proposed migration/refactor strategy;
9. files that would be modified;
10. ADRs that are required.

Do not rewrite the application from scratch unless you demonstrate why the current implementation cannot be safely evolved.

Do not add microservices.

Do not implement LinkedIn scraping or unofficial LinkedIn automation.

After the assessment, implement only the approved PHASE 0 foundation items that can be introduced safely without destroying working functionality.

Run all available tests and builds.

Create/update documentation for every architectural change.

Stop after PHASE 0 and provide a completion report.
```

---

# 57. Business success criteria

TalentIA debe demostrar que puede:

```text
Replace spreadsheet-based candidate tracking
Create one Candidate 360
Reduce duplicate candidate handling
Improve provider visibility/control
Reuse historical candidates
Reduce manual registration effort
Improve relevance of shortlists
Preserve complete recruitment history
Provide auditable metrics
Operate securely inside TCS
Scale beyond the pilot without redesigning the core
```

La decisión futura de evitar la compra de un ATS comercial debe sustentarse en métricas, seguridad, capacidad operativa, soporte y costo total, no solamente en una demo funcional.

---

# 58. Regla final de arquitectura

TalentIA debe ser diseñado como producto empresarial desde la primera migración, pero implementado incrementalmente.

```text
Enterprise architecture
        +
Small controlled increments
        +
Measurable business value
        +
Quality gates
        =
TalentIA
```
