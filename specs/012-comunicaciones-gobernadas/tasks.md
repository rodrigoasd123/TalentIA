# Tareas — SPEC-012

- [x] **T-012-001 — Versionar y aprobar plantillas**
  - Cubre: FR-012-001, AC-012-001
  - Archivos: entidades, repositorios y `email_service.py`
  - Verificación: pruebas de plantilla aprobada y variables
  - Dependencias: ninguna
- [x] **T-012-002 — Validar destinatario e idempotencia**
  - Cubre: FR-012-003, AC-012-002, AC-012-003
  - Archivos: servicio de correo y políticas
  - Verificación: `test_el_destinatario_es_siempre_el_correo_registrado` y duplicados
  - Dependencias: T-012-001
- [x] **T-012-003 — Mantener Gmail sin efectos**
  - Cubre: FR-012-002, AC-012-001
  - Archivos: `app/infrastructure/email/gmail_adapter.py`, configuración
  - Verificación: cero llamadas externas con `DRY_RUN`
  - Dependencias: T-012-002
- [x] **T-012-004 — Autorizar y auditar borradores**
  - Cubre: FR-012-001–FR-012-003, AC-012-001–AC-012-003
  - Archivos: rutas `/emails*`, RBAC y auditoría
  - Verificación: pruebas API y de mensajes sensibles
  - Dependencias: T-012-001–T-012-003

## Puertas de salida

- [x] Todos los requisitos obligatorios están cubiertos.
- [x] No quedan bloqueantes.
- [x] El piloto no produce efectos externos.
