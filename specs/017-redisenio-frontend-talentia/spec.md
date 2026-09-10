---
id: SPEC-017
titulo: Rediseño integral del frontend TalentIA
estado: BORRADOR
responsable_producto: Usuario
creado: 2026-09-10
actualizado: 2026-09-10
---

# SPEC-017 — Rediseño integral del frontend TalentIA

## Problema

El frontend Streamlit actual expone las capacidades principales, pero conserva nombres, navegación y patrones visuales surgidos durante la consolidación. No existe aún evidencia completa de responsive, accesibilidad, consistencia de estados ni una identidad única de TalentIA.

## Resultado esperado

Una experiencia empresarial coherente llamada TalentIA que reutilice los endpoints y flujos existentes, centralice estilos, sesión, permisos y errores, y funcione de extremo a extremo en escritorio, tablet y móvil.

## Alcance propuesto

- Renombrar la experiencia visible a TalentIA.
- Sistema visual común, navegación por rol y componentes reutilizables.
- Login, dashboard, vacantes, candidatos/ingreso, importación histórica, evaluación, revisión, pipeline, Candidate 360, agente, auditoría y configuración.
- Estados de carga, proceso, éxito, validación, conexión, vacío, sesión expirada, acceso denegado, deshabilitado y conflicto de versión.
- Accesibilidad por teclado, foco visible, contraste WCAG AA y diseño responsive.
- Botones y controles legibles permanentemente, sin depender de hover.
- Separación entre estilos, API, sesión/permisos, estado y presentación.

## Fuera de alcance

- Cambiar reglas del backend, esquema de datos o contratos sin refinamiento explícito.
- Implementar endpoints ficticios, autenticación nueva, LinkedIn automático o correo real.
- Retirar el frontend heredado antes de verificar la nueva experiencia.

## Requisitos propuestos

- **FR-017-001:** toda identidad visible debe usar TalentIA, salvo referencias técnicas históricas.
- **FR-017-002:** la navegación debe mostrar exclusivamente páginas y acciones autorizadas para el rol activo.
- **FR-017-003:** cada flujo principal debe representar estados normales, vacíos y fallidos sin perder datos recuperables.
- **FR-017-004:** el frontend debe consumir exclusivamente la API y no duplicar reglas de negocio.
- **FR-017-005:** los flujos complejos deben dividirse en pasos revisables con confirmación para acciones sensibles.
- **NFR-017-001:** escritorio, laptop, tablet y móvil deben ser utilizables sin scroll anidado innecesario.
- **NFR-017-002:** navegación por teclado, foco, etiquetas, contraste y comunicación no basada solo en color.
- **SEC-017-001:** no almacenar o mostrar contraseñas, JWT, API keys, PII no autorizada ni trazas internas.
- **SEC-017-002:** contenido de CV y respuestas no debe insertarse como HTML no confiable.

## Dependencias

SPEC-005 a SPEC-016 son las fuentes funcionales. FastAPI en `http://127.0.0.1:8000` sigue siendo la autoridad de datos y permisos.

## Preguntas abiertas antes de planificar

- Confirmar si se mantiene Streamlit o se autoriza migración de framework.
- Confirmar prioridad entre responsive móvil y densidad operativa de escritorio.
- Confirmar si el frontend nuevo reemplaza al actual tras verificación o convive durante una transición.

## Puerta de aprobación

Esta spec no autoriza cambios de frontend. Requiere refinamiento de las preguntas abiertas y aprobación explícita antes de generar plan o tareas.

## Historial

- 2026-09-10: borrador creado a partir del prompt UX/UI adaptado a TalentIA; implementación no autorizada.
