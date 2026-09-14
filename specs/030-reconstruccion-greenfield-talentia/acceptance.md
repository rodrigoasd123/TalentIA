# Aceptacion - SPEC-030

- **AC-030-001** `[FR-030-001, NFR-030-002]`: instalacion y smoke funcionan solo con
  Python y navegador, sin proveedor IA.
- **AC-030-002** `[FR-030-002, SEC-030-001]`: autenticacion, permisos, cliente e IDOR se
  prueban con denegacion predeterminada.
- **AC-030-003** `[FR-030-003]`: los flujos operativos P0 persisten, versionan y auditan sus
  cambios.
- **AC-030-004** `[FR-030-004]`: agentes deterministicos son explicables; AG-02/03 nunca
  deciden ni usan salida propia como evidencia.
- **AC-030-005** `[FR-030-005]`: jobs y checkpoints sobreviven reinicios y no duplican
  efectos.
- **AC-030-006** `[NFR-030-001]`: pruebas de arquitectura bloquean dependencias prohibidas.
- **AC-030-007** `[OPS-030-001]`: migracion, backup, restore y verificacion son
  reproducibles en Windows.
- **AC-030-008**: toda capacidad afectada por `BIZ-XXX` permanece bloqueada o requiere
  revision humana y queda documentada.

