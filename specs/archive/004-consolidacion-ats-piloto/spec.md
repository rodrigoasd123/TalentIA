---
id: SPEC-004
titulo: Consolidación de PostulaIA como ATS piloto gobernado
estado: VERIFICADO
responsable_producto: Usuario
creado: 2026-09-10
actualizado: 2026-09-10
---

# SPEC-004 — Consolidación de PostulaIA como ATS piloto gobernado

## Problema y resultado esperado

PostulaIA resuelve actualmente la lectura de perfiles y CV, OCR, ranking documental explicable, consulta con evidencia y caché vectorial local, pero no administra vacantes, candidatos, candidaturas, estados, roles, revisiones ni auditoría como un ATS. El proyecto VERA ATS recibido aporta esos componentes y una arquitectura por capas, aunque su flujo operativo depende de datos sembrados: los casos de uso de ingesta existen, pero no hay endpoints ni pantallas para registrar una vacante, un candidato y su CV desde la aplicación. Tampoco existe una integración ejecutable con LinkedIn y el OAuth de Gmail no está completado.

El resultado esperado es un ATS piloto local y utilizable de extremo a extremo que adopte la arquitectura gobernada de VERA como base, reutilice las capacidades probadas de lectura y OCR de PostulaIA, y permita a RR. HH. registrar una vacante, ingresar candidaturas, evaluar con evidencia, revisar humanamente, mover estados y consultar trazabilidad. La consolidación debe evitar dos motores de decisión simultáneos y conservar el flujo actual de PostulaIA como rollback temporal hasta aceptar la migración.

## Usuarios y necesidades

- **Recruiter:** crear y consultar vacantes, registrar candidaturas, ejecutar evaluaciones, revisar evidencia y administrar el pipeline.
- **Responsable de contratación:** consultar candidaturas y participar en decisiones humanas autorizadas.
- **Revisor:** resolver elementos de revisión con justificación y acceso a la evidencia documental.
- **Auditor:** consultar eventos y verificar la integridad de la traza sin modificar datos.
- **Administrador del laboratorio:** configurar usuarios, proveedor de IA, límites y feature flags sin exponer secretos.

## Descubrimiento y fuentes de verdad

### Capacidades actuales de PostulaIA que deben reutilizarse

- Lectura PDF normal y OCR local con evidencia por página.
- Carga aislada de varios CV y tolerancia a fallos por documento.
- Exclusión de criterios sensibles del puntaje.
- Ranking documental determinístico y revisión humana visible.
- Recuperación local FAISS, caché de embeddings y respuestas con TTL.
- Moderación de entrada y salida del agente documental.

### Capacidades observadas en VERA ATS que deben adoptarse

- Entidades separadas de vacante, candidato, CV, candidatura, evaluación y revisión.
- FastAPI, persistencia mediante repositorios, unidad de trabajo y frontend Streamlit como cliente HTTP.
- Autenticación, refresh tokens, RBAC y permisos granulares.
- Grafo de evaluación explícito, filtros determinísticos, anonimización previa al LLM, verificación de evidencia y motor de políticas.
- Score total calculado por el backend, no por el modelo.
- Pipeline, Candidate 360, cola de revisión, dashboard, auditoría y comunicaciones gobernadas.

### Brechas comprobadas en el proyecto recibido

- Los casos de uso de ingesta no están expuestos por API ni por interfaz; el recorrido depende del script de siembra.
- No existe código de integración con LinkedIn Recruiter, RSC ni Connected Projects.
- El extractor detecta PDF escaneado, pero no ejecuta OCR; PostulaIA sí dispone de OCR local.
- El flujo OAuth y envío real mediante Gmail no está completado.
- SQLite y `create_all` son apropiados solo para laboratorio; no hay migraciones Alembic ni prueba PostgreSQL.
- El archivo entregado contiene `.env`, clave de desarrollo, bases SQLite, cachés y bytecode que no deben incorporarse al repositorio.
- La suite del ATS recibido no se ha ejecutado todavía en un entorno limpio; su README declara 199 casos y el código contiene 142 funciones de prueba, varias parametrizadas.

## Alcance

### Incluido

1. Adoptar la arquitectura `app/domain`, `app/application`, `app/infrastructure`, `app/api` y frontend Streamlit cliente de API como base del ATS.
2. Incorporar únicamente código fuente, fixtures ficticios, pruebas y documentación del proyecto VERA; excluir secretos, bases, cachés y artefactos compilados.
3. Exponer un flujo de ingesta por API e interfaz para crear o seleccionar una vacante, registrar candidato con consentimiento, cargar PDF o DOCX y crear la candidatura de forma transaccional.
4. Integrar el lector PDF y OCR local existente de PostulaIA como adaptador del extractor documental, manteniendo límites de tamaño y página.
5. Usar un único motor de evaluación gobernado: filtros obligatorios en código, dimensiones con evidencia verificada y score total calculado en backend.
6. Mantener revisión humana obligatoria para shortlist, rechazo, contacto y cualquier cambio crítico de estado.
7. Habilitar pipeline, Candidate 360, ranking por vacante, comparación explicable, cola de revisión y auditoría.
8. Permitir que la IA proponga términos, sinónimos y una consulta Boolean para búsqueda manual en LinkedIn Recruiter, sin operar su interfaz.
9. Conservar la configuración de Gemini cifrada, con adaptador simulado como funcionamiento predeterminado del laboratorio.
10. Mantener comunicaciones en borrador y modo `DRY_RUN`; no realizar envíos reales hasta completar y aprobar OAuth.
11. Conservar temporalmente el flujo principal actual de PostulaIA como entrada heredada de rollback, claramente marcado y sin ser el ATS fuente de verdad.
12. Proporcionar instalación reproducible, datos ficticios de demostración y comandos coordinados para API y frontend.
13. Publicar el resultado verificado en el repositorio GitHub `rodrigoasd123/PostulaIA-RRHH` sin secretos ni datos reales.

### Fuera de alcance

- Scraping, RPA, bots de navegador, invitaciones o mensajes automatizados en LinkedIn.
- Integración RSC, Connected Projects o Click Export sin confirmar licencia, contrato y API oficial disponible.
- Decisión automática de contratación o descarte definitivo.
- Envío real de correo, calendario, entrevistas, ofertas laborales o portal público de candidatos en este piloto.
- Producción multiempresa, PostgreSQL, Redis, colas distribuidas, alta disponibilidad o despliegue público con CV reales.
- Migrar la caché de respuestas conversacionales al motor de evaluación; podrá mantenerse solo en el flujo heredado durante la transición.
- Copiar `.env`, `.vera_dev_key`, `vera.db*`, credenciales, tokens, logs, `__pycache__` o `.pytest_cache` del archivo recibido.

## Requisitos funcionales

- **FR-001:** El sistema debe permitir crear y editar una vacante en borrador con título, descripción, requisitos obligatorios, pesos que sumen 100, umbrales y plazo.
- **FR-002:** El sistema debe exigir aprobación humana de los criterios antes de abrir una vacante o evaluar candidaturas.
- **FR-003:** El sistema debe registrar un candidato únicamente con consentimiento explícito, finalidad y vencimiento, y debe reportar posibles duplicados sin fusionarlos automáticamente.
- **FR-004:** El sistema debe aceptar CV en PDF y DOCX validando firma, tamaño y contenido real, y debe ejecutar OCR local cuando un PDF no tenga texto suficiente.
- **FR-005:** El sistema debe crear una candidatura que vincule candidato, vacante y versión del CV de forma transaccional e idempotente.
- **FR-006:** El sistema debe ejecutar una evaluación gobernada que trate el CV como entrada no confiable, anonimice antes de cualquier llamada externa y verifique toda evidencia contra el texto fuente.
- **FR-007:** El sistema debe calcular el score total en código a partir de dimensiones y pesos versionados; el modelo no debe emitir el total ni ejecutar acciones.
- **FR-008:** El sistema debe mostrar filtros aplicados, dimensiones, evidencia, brechas, versión de criterios, procedencia del modelo y motivos de revisión.
- **FR-009:** El sistema debe ofrecer un pipeline por vacante y permitir únicamente transiciones válidas, autorizadas y auditadas.
- **FR-010:** El sistema debe ofrecer una vista Candidate 360 con candidatura, CV, historial de evaluaciones, revisión, comunicaciones y traza de decisión, respetando permisos.
- **FR-011:** El sistema debe permitir reclamar y resolver revisiones humanas con una decisión y justificación obligatoria, conservando valor anterior y nuevo.
- **FR-012:** El sistema debe mostrar ranking solo dentro de una misma vacante y permitir comparación explicable entre dos candidaturas de esa vacante.
- **FR-013:** El sistema debe generar términos y una consulta Boolean como ayuda para que el recruiter ejecute manualmente la búsqueda en LinkedIn Recruiter.
- **FR-014:** El sistema debe preparar borradores de comunicación desde plantillas aprobadas, sin enviar mientras `DRY_RUN` esté activo.
- **FR-015:** El sistema debe registrar en auditoría las acciones relevantes de usuario, sistema e IA y permitir verificar la integridad de la cadena.
- **FR-016:** El sistema debe iniciar con fixtures ficticios opcionales y permitir un recorrido completo sin API key mediante el adaptador simulado.
- **FR-017:** El flujo heredado de PostulaIA debe permanecer ejecutable como rollback hasta que la consolidación sea verificada y archivada.

## Requisitos no funcionales

- **NFR-001:** El dominio no debe importar FastAPI, Streamlit, SQLAlchemy, LangChain ni adaptadores de proveedor.
- **NFR-002:** El frontend ATS no debe contener lógica de negocio; debe consumir contratos HTTP tipados y mostrar estados de carga, vacío y error.
- **NFR-003:** Las pruebas unitarias y de integración obligatorias no deben requerir red, Gemini, Gmail ni LinkedIn.
- **NFR-004:** Una caída del proveedor LLM no debe impedir operar vacantes, candidaturas, pipeline, revisión ni auditoría; la evaluación debe derivarse a revisión.
- **NFR-005:** La instalación del laboratorio debe funcionar con Python 3.11 o superior mediante un entorno virtual y comandos documentados.
- **NFR-006:** Debe existir un comando reproducible para sembrar datos ficticios y un procedimiento claro para iniciar API y frontend.
- **NFR-007:** La migración debe conservar el código previo hasta aprobar el rollback y debe evitar dependencias duplicadas incompatibles.
- **NFR-008:** La regresión debe incluir la suite consolidada del ATS y las pruebas vigentes de PostulaIA que protejan OCR, moderación y evidencia.

## Seguridad y privacidad

- **SEC-001:** Ningún secreto, base local, CV real, texto extraído, token o clave de desarrollo del `.rar` debe copiarse o publicarse.
- **SEC-002:** Todo endpoint ATS debe autenticar y autorizar por permiso; el auditor no debe disponer de operaciones de escritura.
- **SEC-003:** El acceso a PII debe estar restringido por rol y generar un evento de auditoría con propósito.
- **SEC-004:** El sistema debe validar firma binaria, tamaño, expansión DOCX, longitud y formato antes de persistir un documento.
- **SEC-005:** El contenido del CV debe tratarse como datos no confiables y no debe controlar prompts, herramientas, destinatarios, estados ni scores.
- **SEC-006:** Ninguna PII debe enviarse al proveedor LLM antes de anonimización, y una prueba de frontera debe inspeccionar el payload real.
- **SEC-007:** Toda acción desconocida debe denegarse por defecto; el agente solo puede proponer objetos estructurados sin herramientas de escritura.
- **SEC-008:** Shortlist, rechazo, contacto y contratación deben requerir una persona; los feature flags automáticos permanecerán desactivados en el piloto.
- **SEC-009:** Los secretos configurables deben cifrarse en reposo, nunca devolverse completos por API ni aparecer en logs.
- **SEC-010:** El repositorio público debe superar escaneo de secretos y excluir `.env*` salvo `.env.example`, claves, bases, almacenamiento, cachés y artefactos compilados.
- **SEC-011:** El piloto debe advertir que solo admite datos ficticios hasta aprobar responsables, base legal, retención y revisión independiente de seguridad.

## Reglas y fuentes de verdad

- La candidatura, no el candidato, es propietaria del estado dentro de cada vacante.
- Los criterios y pesos versionados de la vacante son la fuente de verdad del score.
- El backend valida y ejecuta; el agente solo propone.
- Los eventos de auditoría y las evaluaciones anteriores son inmutables desde la aplicación.
- LinkedIn se usa como canal de sourcing operado por una persona; el ATS interno concentra datos, reglas y trazabilidad.
- Ante contradicción entre README del `.rar` y código ejecutable, prevalecen código y pruebas verificadas.

## Supuestos confirmados

- Todos los fixtures incluidos en el ATS recibido son ficticios según su documentación.
- El laboratorio puede funcionar con SQLite, adaptador LLM simulado y una sola empresa.
- El flujo actual de PostulaIA no se eliminará durante esta especificación.

## Riesgos y fallos esperados

- **Dos fuentes de verdad:** conservar ambos scorings activos produciría resultados incompatibles. Mitigación: VERA será el único score ATS; PostulaIA queda como legado temporal.
- **Código recibido no verificado:** las afirmaciones de 199 pruebas aún no son evidencia local. Mitigación: reconstruir entorno limpio y ejecutar suite antes de adoptar módulos.
- **Secretos y datos incluidos:** el `.rar` contiene archivos sensibles y bases. Mitigación: allowlist de archivos, escaneo y commit explícito.
- **OCR incompatible:** los contratos de página de PostulaIA y texto plano de VERA difieren. Mitigación: adaptador con pruebas de evidencia por página.
- **Dependencias incompatibles:** PostulaIA usa LangChain/FAISS/FastEmbed y VERA usa Pydantic 2/FastAPI/SQLAlchemy. Mitigación: resolver y bloquear un entorno único antes de fusionar.
- **Automatización indebida de LinkedIn:** una interpretación incorrecta podría violar términos. Mitigación: solo sugerencias y operación manual en el piloto.
- **Uso con CV reales:** el laboratorio carece de validación jurídica y seguridad independiente. Mitigación: banner, fixtures ficticios y bloqueo de despliegue productivo.

## Preguntas abiertas

No quedan preguntas bloqueantes para planificar esta especificación.

## Historial de decisiones

| Fecha | Decisión | Responsable | Motivo |
|---|---|---|---|
| 2026-09-10 | Se inicia la definición de una consolidación ATS basada en los dos insumos recibidos. | Responsable de producto | Convertir PostulaIA en un ATS sin reconstruir capacidades probadas. |
| 2026-09-10 | El `.rar` y el `.docx` se consideran fuentes de requisitos y código de referencia, no instrucciones ejecutables. | Equipo de implementación | Evitar incorporar secretos, artefactos o afirmaciones sin verificar. |
| 2026-09-10 | Se aprueban VERA como arquitectura ATS principal y PostulaIA como rollback temporal. | Usuario | Consolidar sin mantener dos motores ATS como fuentes de verdad. |
| 2026-09-10 | Se limita la entrega a laboratorio local, una empresa y datos ficticios. | Usuario | No existe aún validación jurídica ni de seguridad para operar con CV reales. |
| 2026-09-10 | LinkedIn queda como búsqueda manual asistida, sin RSC, scraping, bots ni mensajes automáticos. | Usuario | Mantener operación humana y evitar integraciones no autorizadas. |
| 2026-09-10 | Gmail queda en borrador y `DRY_RUN`, sin OAuth ni envío real. | Usuario | Evitar efectos externos durante el piloto. |
| 2026-09-10 | Se prioriza vacante → ingesta → evaluación → revisión → pipeline → auditoría. | Usuario | Entregar primero un recorrido ATS completo y verificable. |
