# SPEC-033 — Panel administrativo de IA y trazas MLflow

- **Estado:** VERIFICADA
- **Fecha:** 2026-09-14
- **Aprobador:** Usuario

## Problema y resultado

Administracion necesita gestionar proveedor, modelo, credencial y parametros sin reiniciar, probar
la conexion y observar ejecuciones de LangGraph por modelo. El resultado debe conservar el modo
local, la revision humana, SQLite y la privacidad del CV.

## Alcance

- Ruta exclusiva /admin/configuracion-ia, diagnóstico HTMX y badge global.
- Catálogo OpenAI, Gemini y local solicitado.
- Configuración compartida servidor/worker en SQLite con secreto cifrado y write-only.
- Cliente HTTP gobernado para sugerencias de AG-03 después de sanitización.
- Trazas MLflow padre/hijo metadata-only con nodos, latencia y tokens.
- Enlace confiable al MLflow local y benchmark existente.

## Fuera de alcance

- Aprovisionar cuotas, validar comercialmente la disponibilidad de un modelo o activar ganadores
  de benchmark automáticamente.
- Guardar prompts, respuestas, CV, PII o secretos en telemetría.
- Convertir una sugerencia de IA en decisión final.

## Requisitos

- **FR-033-001:** solo administrador accede, guarda y diagnostica.
- **FR-033-002:** estado local, pendiente, activo o error muestra proveedor, modelo, latencia y
  última verificación sin revelar secretos.
- **FR-033-003:** el cambio de proveedor/modelo/parámetros se comparte con el worker sin reinicio.
- **FR-033-004:** el diagnóstico clasifica errores y se actualiza con HTMX.
- **FR-033-005:** el header muestra el estado global y enlaza al panel solo para administración.
- **FR-033-006:** MLflow registra workflow y nodos con latencia y tokens por modelo.
- **FR-033-007:** una sugerencia externa requiere evidencia localizable en el original.
- **NFR-033-001:** MLflow y proveedores externos son opcionales y degradables.
- **NFR-033-002:** la migración SQLite tiene upgrade y downgrade.
- **SEC-033-001:** credenciales cifradas, write-only y ausentes de logs/UI/trazas.
- **SEC-033-002:** sanitización e inyección se validan antes de red.
- **SEC-033-003:** CSRF, RBAC y bloqueo optimista protegen mutaciones.

## Decisiones de seguridad

La UI indica si existe una clave, pero no muestra prefijos o sufijos: prevalece la política
write-only ya aprobada en SPEC-023. Las etiquetas de cuota del catálogo no garantizan cuota real;
el proveedor es la única autoridad.

## Rollback

Seleccionar modo local, revertir código y aplicar downgrade de 0005 a 0004. El ATS determinista
continúa operativo y los históricos de evaluación no se eliminan.
