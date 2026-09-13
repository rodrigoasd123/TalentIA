# Plan - SPEC-030

1. Congelar el sistema previo como referencia y crear `src/talentia`.
2. Construir dominio puro y contratos de aplicacion.
3. Implementar persistencia SQLAlchemy y migraciones Alembic independientes.
4. Exponer API y web sin acceso directo a ORM.
5. Incorporar agentes, jobs, checkpoints y fallback manual.
6. Completar seguridad, auditoria, metricas y operacion del piloto.
7. Verificar arquitectura, migraciones, API, seguridad, workflows y smoke.

## Migracion y rollback

La nueva base usa `talentia_greenfield.db` y no modifica `talentia.db`. Para volver atras se
detiene el nuevo entrypoint y se inicia el anterior. La promocion de datos queda fuera de
alcance hasta resolver las decisiones de identidad, retencion y campos sensibles.

