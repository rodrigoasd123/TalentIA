# SPEC-023 — Catálogo y proveedores de modelos de IA

- **Estado:** VERIFIED
- **Fecha:** 2026-09-12
- **Owner:** Product and engineering

## Problema y resultado esperado

Los commits recientes añadieron Gemini directo, GenAI Lab y OpenAI sin una spec propietaria. El catálogo, las credenciales y el modelo realmente invocado deben ser coherentes y verificables.

## Usuarios y alcance

- Administración configura y prueba modelos sin exponer secretos.
- RR. HH. recibe procedencia real del proveedor y modelo.
- Incluye catálogo por capacidad, claves separadas, fábrica desacoplada y fallback simulado.
- Excluye aprovisionar cuentas/saldo y elegir modelos sin benchmark aprobado.

## Requisitos

- **FR-023-001:** el selector debe mostrar solo modelos de generación y resolver su proveedor internamente.
- **FR-023-002:** una llamada debe usar exactamente el modelo solicitado y registrar el modelo real devuelto.
- **FR-023-003:** cada proveedor debe usar su propia credencial sin reutilización silenciosa.
- **FR-023-004:** el panel debe probar la credencial con una generación JSON mínima.
- **NFR-023-001:** toda dependencia importada debe declararse en requirements y paquete.
- **NFR-023-002:** el ATS determinista debe operar sin credenciales externas.
- **SEC-023-001:** las claves no deben aparecer en logs, respuestas, Git ni trazas.
- **SEC-023-002:** solo `settings:write` puede modificar o probar credenciales/modelos.

## Restricciones y riesgos

- La free tier solo admite datos sintéticos hasta aprobación Security/Legal.
- Una entrada de catálogo no demuestra disponibilidad; prevalece la prueba explícita.
- No hay preguntas bloqueantes: el documento TCS y la constitución fijan el alcance.

## Referencias

`docs/sdd/constitucion.md`, ADR-007 y SPEC-014.
