# SPEC-030 - Reconstruccion greenfield de TalentIA

- **Estado:** VERIFICANDO
- **Fase activa:** Fase 3 - Interfaz de evaluacion y revision humana
- **Inicio de fase:** 2026-09-13
- **Implementacion de fase concluida:** 2026-09-13
- **Fuente ejecutable:** `IMPLEMENTATION_SPEC.md`
- **Metodo:** Spec-Driven Development

## Problema

La implementacion anterior concentra capacidades validas, pero no cumple la arquitectura
greenfield aprobada para el piloto: monolito modular, frontend Jinja2/HTMX, trabajo de IA
durable y alcance obligatorio por cliente.

## Usuarios

- Administracion del piloto.
- Reclutamiento y seleccion.
- Gestores de contratacion.
- Revision humana y auditoria.

## Alcance

Implementar `IMP-001` a `IMP-035` de `IMPLEMENTATION_SPEC.md` sin conservar contratos
obligatorios del sistema anterior. El sistema anterior permanece solo como referencia y
rollback mientras se valida el nuevo entrypoint `talentia.main:app`.

## Requisitos

- **FR-030-001:** ofrecer una aplicacion Python instalable con FastAPI, Jinja2, HTMX local,
  SQLAlchemy, Alembic y SQLite WAL.
- **FR-030-002:** implementar autenticacion, RBAC y alcance por cliente en todos los casos de
  uso y endpoints sensibles.
- **FR-030-003:** gestionar identidad, candidatos, perfiles versionados, postulaciones,
  documentos, evaluaciones, revisiones, lotes, excolaboradores, exclusiones y metricas.
- **FR-030-004:** ejecutar AG-01/04/05 deterministicamente y mantener AG-02/03 gobernados,
  estructurados, con evidencia y fallback manual.
- **FR-030-005:** ofrecer trabajos durables, checkpoints, reintentos e idempotencia sin
  mantener transacciones abiertas durante trabajo externo.
- **NFR-030-001:** respetar los limites de dependencias entre dominio, aplicacion,
  infraestructura, API y presentacion.
- **NFR-030-002:** funcionar sin Node.js y sin proveedor LLM.
- **SEC-030-001:** proteger sesiones, CSRF, alcance IDOR, uploads, PII, campos sensibles,
  exportaciones y auditoria.
- **OPS-030-001:** incluir migracion, arranque, worker, backup, restore y verificacion del
  piloto para Windows.

## Decisiones bloqueadas

`BIZ-001` a `BIZ-010` permanecen bloqueadas. Las transiciones, retencion, identidad dudosa,
tratamiento de evidencia ausente y datos BGC/Equifax afectados fallan de forma cerrada o
requieren revision humana. No se inventan reglas de negocio.

## Fuera de alcance

- Despliegue compartido o productivo.
- Decisiones autonomas de contratacion.
- Contacto automatico, scraping o simulaciones presentadas como resultados reales.
- Resolucion implicita de cualquier `BIZ-XXX`.
