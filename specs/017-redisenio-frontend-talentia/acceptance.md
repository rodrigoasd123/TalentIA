# Aceptación — SPEC-017

## AC-017-001 — Identidad y shell

Todas las páginas autenticadas comparten barra lateral, cabecera y sistema visual TalentIA; la página activa es identificable y el contenido principal puede alcanzarse mediante un enlace de salto.

## AC-017-002 — Dashboard real

El inicio presenta los candidatos recientes, el estado real del proveedor y la revisión humana, sin valores ficticios, además de accesos a flujos ya disponibles.

## AC-017-003 — Componentes operativos

Listados, tablas, fichas, formularios, alertas, estados, vacíos y acciones mantienen una apariencia y jerarquía consistentes sin cambiar contratos.

## AC-017-004 — Responsive y accesibilidad

La navegación, sesión y acciones esenciales permanecen utilizables en escritorio, tablet y móvil; existe foco visible y el significado de los estados incluye texto.

## AC-017-005 — Seguridad y compatibilidad

No se incorporan recursos remotos, HTML no confiable, nuevas dependencias ni cambios de backend. Los nombres, IDs, rutas, variables, formularios y atributos HTMX existentes permanecen operativos.

## AC-017-006 — Validación y rollback

Las pruebas frontend estructurales y la regresión completa pasan. El cambio se revierte restaurando plantillas y CSS, sin migraciones ni pérdida de datos.
