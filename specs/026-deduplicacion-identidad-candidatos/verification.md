# Verificación — SPEC-026

- El preflight ocurre antes del procesamiento del CV y consulta DNI, correo, teléfono y nombre normalizado.
- Las coincidencias muestran correo enmascarado e historial; nunca fusionan automáticamente.
- Pruebas añadidas para DNI, nombre con/sin tildes y endpoint preflight.
- Evidencia global: `310 passed`.

## Refinamiento 2026-09-14

- Pruebas focalizadas: `8 passed`; cubren teléfono probable con confirmación y una coincidencia en
  la posición 205.
- La prueba de nombre normalizado ahora espera revisión probable, no un bloqueo definitivo.
- `BIZ-004` sigue pendiente; no existe umbral aproximado inventado.
- Suite greenfield: `89 passed, 2 warnings in 95.83s`.
- Ruff y formato: aprobados sobre 89 archivos; mypy: 65 archivos sin errores.
- Scanner: 348 archivos seguros; identidad visible aprobada.
- El run `34821866388` aprobó; estado `VERIFICADO`. `BIZ-004` continúa fuera del alcance.
