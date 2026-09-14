---
id: SPEC-017
titulo: Rediseño visual corporativo del frontend TalentIA
estado: VERIFICANDO
responsable_producto: Usuario
creado: 2026-09-10
actualizado: 2026-09-14
---

# SPEC-017 — Rediseño visual corporativo del frontend TalentIA

## Problema

La interfaz web funciona, pero presenta una jerarquía visual básica, patrones inconsistentes entre páginas y una adaptación móvil que oculta navegación y sesión. Esto dificulta escanear tablas, reconocer estados y completar formularios operativos con confianza.

## Resultado esperado

Una experiencia corporativa, clara y consistente para el ATS TalentIA, construida sobre el frontend existente y ejecutable mediante el mismo proceso Python. La mejora no cambia datos, permisos, rutas, formularios ni reglas del producto.

## Decisiones aprobadas

- Se conserva FastAPI con plantillas Jinja2.
- Se conservan Bootstrap y HTMX servidos localmente, junto con CSS y JavaScript vanilla.
- El diseño es desktop-first y usable en tablet y móvil.
- La interfaz actual se mejora en el mismo flujo; no se crea una aplicación paralela.
- No se incorpora Node, npm, TypeScript, bundlers, frameworks ni servicios frontend.

## Alcance

- Sistema de diseño centralizado mediante variables CSS para color, tipografía, espacio, bordes, sombras, foco y estados.
- Shell corporativo con barra lateral, navegación agrupada, página activa, cabecera, contexto de sesión y modo manual.
- Dashboard con jerarquía, accesos directos y exclusivamente datos reales ya entregados por el backend.
- Tablas, buscadores, fichas, formularios, estados, alertas, vacíos, evaluaciones y progreso con patrones consistentes.
- Login alineado con la identidad visual del producto.
- Responsive sin ocultar capacidades esenciales, navegación por teclado y foco visible.
- Pruebas estructurales del HTML y del sistema de diseño, además de la regresión existente.

## Fuera de alcance

- Backend, API, persistencia, modelos, servicios, autenticación, autorización o reglas de negocio.
- Rutas, URL, nombres/IDs de campos, variables, bucles, condiciones, atributos HTMX o contratos existentes.
- Métricas inventadas, datos simulados o nuevas capacidades funcionales.
- Nuevas dependencias o herramientas obligatorias de construcción.

## Requisitos

- **FR-017-001:** todas las páginas deben compartir una identidad visual TalentIA coherente.
- **FR-017-002:** la navegación debe conservar destinos existentes, indicar la sección activa y seguir disponible en resoluciones reducidas.
- **FR-017-003:** dashboard, listados, detalle, formularios y estados deben tener jerarquía y componentes consistentes.
- **FR-017-004:** el dashboard debe mostrar solo información real disponible en su contexto actual.
- **FR-017-005:** todos los contratos de formularios, HTMX y plantillas deben conservarse.
- **NFR-017-001:** la interfaz debe ser usable desde 390 px sin scroll horizontal de página; las tablas pueden desplazarse dentro de su contenedor.
- **NFR-017-002:** debe existir foco visible, enlace para saltar al contenido, etiquetas accesibles y estados que no dependan solo del color.
- **NFR-017-003:** los recursos deben permanecer locales y el arranque debe seguir siendo exclusivamente Python.
- **NFR-017-004:** la mejora no debe añadir solicitudes de red, fuentes remotas ni dependencias de ejecución.
- **SEC-017-001:** no se expondrán secretos, tokens, trazas internas ni PII adicional.
- **SEC-017-002:** los datos no confiables seguirán renderizándose con el escape de Jinja, nunca como HTML sin sanitizar.

## Compatibilidad y rollback

Los cambios se limitan a plantillas, CSS y pruebas. El rollback consiste en revertir esos archivos; no requiere migración ni transformación de datos. La regresión web y backend debe permanecer verde.

## Aprobación

El usuario aprobó explícitamente el rediseño completo el 2026-09-14 bajo la condición de no romper el código ni el flujo. Esa aprobación resuelve las preguntas del borrador anterior y autoriza planificación e implementación dentro de este alcance.

## Historial

- 2026-09-10: borrador inicial.
- 2026-09-14: refinada y aprobada para implementación visual sobre el stack existente.
