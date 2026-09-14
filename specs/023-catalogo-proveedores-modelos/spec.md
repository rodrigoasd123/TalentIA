# SPEC-023 — Catálogo y proveedores de modelos de IA

- **Estado:** VERIFIED (línea base y refinamiento R1)
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

## Refinamiento R1 — Panel administrable de proveedores y modelos

> Refinamiento aprobado por el propietario el 2026-09-13.

### Necesidad

La línea base permite seleccionar modelos de un catálogo fijo y guardar credenciales separadas.
Administración necesita gestionar desde la interfaz qué proveedores y modelos están disponibles,
sin editar código ni archivos de entorno y sin perder el fallback actual.

### Alcance propuesto

- Panel exclusivo de administración para listar, crear, editar, habilitar y deshabilitar
  proveedores y modelos.
- Los proveedores incorporados desde la UI deben usar protocolos ya soportados. En R1 se admite
  `OpenAI compatible`; los adaptadores nativos Gemini y OpenAI continúan como proveedores del
  sistema. Agregar un SDK o protocolo nuevo exige otra aprobación SDD.
- Un proveedor tendrá nombre visible, identificador estable, tipo de adaptador, URL base validada,
  estado y referencia a una credencial cifrada.
- Un modelo tendrá identificador exacto del proveedor, nombre visible, capacidades declaradas,
  estado y, opcionalmente, tarifas de entrada/salida administradas para estimar costo.
- Los proveedores/modelos incluidos con el sistema no podrán eliminarse físicamente; podrán
  deshabilitarse si no están activos ni son necesarios para el fallback.
- La configuración activa podrá asignar un modelo habilitado a cada función soportada. La
  configuración global existente seguirá siendo el fallback para conservar compatibilidad.
- Alta, cambio, prueba, activación y desactivación serán operaciones auditadas.

### Fuera de alcance de R1

- Descargar o instalar SDK arbitrarios desde la interfaz.
- Ejecutar código suministrado por el administrador.
- Descubrir o activar automáticamente modelos del proveedor.
- Borrar históricos de evaluación o telemetría al deshabilitar un modelo.
- Seleccionar automáticamente el “ganador” de un benchmark.

### Requisitos nuevos

- **FR-023-005:** el administrador debe poder registrar un proveedor OpenAI-compatible con
  identificador, nombre, URL base HTTPS y credencial write-only cifrada.
- **FR-023-006:** el administrador debe poder registrar modelos bajo un proveedor habilitado,
  indicando identificador remoto exacto, nombre, capacidades y estado.
- **FR-023-007:** el panel debe permitir habilitar/deshabilitar proveedores y modelos sin borrado
  físico y sin invalidar evaluaciones históricas.
- **FR-023-008:** el administrador debe poder asignar modelos habilitados a funciones soportadas;
  una asignación inválida debe rechazarse de forma atómica.
- **FR-023-009:** el catálogo combinado debe conservar los proveedores/modelos integrados y las
  configuraciones existentes durante la migración.
- **FR-023-010:** el panel debe probar una credencial con una generación JSON mínima y mostrar un
  resultado sanitizado antes de permitir que el proveedor se marque como verificado.
- **NFR-023-003:** los cambios del catálogo deben persistir en SQLite y contar con migración
  reversible probada.
- **NFR-023-004:** deshabilitar o dejar indisponible un proveedor no debe romper los flujos
  deterministas; el fallo de IA deriva a revisión humana o fallback manual.
- **SEC-023-003:** solo `settings:read` puede consultar metadatos del catálogo y solo
  `settings:write` puede mutarlo, probar credenciales o cambiar asignaciones.
- **SEC-023-004:** API, UI, logs, auditoría, errores y MLflow nunca deben devolver la credencial,
  ni siquiera parcialmente; solo deben indicar si está configurada.
- **SEC-023-005:** las URL base deben validarse contra SSRF: HTTPS por defecto, sin credenciales
  embebidas, sin hosts locales/privados fuera del modo laboratorio y sin redirecciones inseguras.
- **SEC-023-006:** toda mutación debe usar CSRF en la UI, validación de concurrencia e idempotencia
  cuando corresponda.

### Compatibilidad y rollback

- `llm.model` y las credenciales actuales se conservan durante la migración y se representan como
  registros del sistema.
- El rollback debe poder volver al catálogo estático sin perder secretos ni alterar resultados
  históricos.
- Ningún proveedor personalizado será requisito para iniciar TalentIA o usar el ATS determinista.

### Decisiones aprobadas para R1

1. R1 permitirá altas dinámicas únicamente mediante el protocolo OpenAI-compatible.
2. Los proveedores nativos incluidos no se eliminan; solo se deshabilitan de forma segura.
3. Las tarifas serán opcionales y administradas; costo desconocido se mostrará como “no
   disponible”, nunca como cero real.
4. Los benchmarks nunca activarán un modelo automáticamente.
