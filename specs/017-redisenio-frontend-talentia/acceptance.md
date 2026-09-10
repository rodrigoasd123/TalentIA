# Aceptación propuesta — SPEC-017

Estos criterios permanecen en borrador hasta aprobación.

## AC-017-001 — Identidad y navegación

Todas las páginas operativas usan TalentIA y la navegación cambia según rol, con sesión y cierre visibles sin exponer tokens.

## AC-017-002 — Flujos completos

Login, vacantes, ingreso, importación, evaluación, revisión, pipeline, Candidate 360, agente, dashboard, auditoría y configuración cubren carga, éxito, vacío y errores recuperables usando endpoints reales.

## AC-017-003 — Responsive y accesibilidad

Los recorridos críticos se verifican a 1440×900, 1280×720, 768×1024 y 390×844; teclado, foco, etiquetas y contraste cumplen la línea base acordada.

## AC-017-004 — Controles legibles

Botones, pestañas, selectores y acciones muestran texto y estado sin hover y no dependen solo del color.

## AC-017-005 — Seguridad de presentación

JWT, claves, contraseñas y trazas no aparecen en UI/logs; el contenido no confiable no se renderiza como HTML y las acciones sensibles requieren confirmación.

## AC-017-006 — Compatibilidad y rollback

La regresión backend permanece verde, los contratos faltantes se documentan antes de cambiarlos y el frontend anterior sigue disponible hasta aprobar la sustitución.
