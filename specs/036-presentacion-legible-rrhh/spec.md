# SPEC-036 - Presentacion legible para RR. HH.

- **Estado:** VERIFIED
- **Fuente:** Solicitud del propietario del 2026-09-14.

## Problema

Algunas vistas muestran identificadores tecnicos de 32 caracteres y valores booleanos crudos. Esto
dificulta reconocer clientes, postulaciones y evaluaciones durante el trabajo diario de RR. HH.

## Requisitos

- **FR-036-001:** las listas de evaluaciones no deben presentar el identificador como texto visible;
  deben mostrar candidato, vacante, puntaje y estado de revision con una accion comprensible.
- **FR-036-002:** las listas de postulaciones deben mostrar persona candidata, vacante, cliente,
  fuente, estado y fecha, sin una columna de identificador tecnico.
- **FR-036-003:** todos los selectores de cliente operativos deben presentar codigo y nombre; el ID se
  conserva exclusivamente como valor interno del formulario.
- **FR-036-004:** las listas de Ex-TCS y exclusiones deben compartir el sistema visual corporativo y
  disponer de busqueda local compatible con la CSP.
- **NFR-036-001:** no cambiar IDs, rutas, relaciones, reglas de negocio ni contratos de API.
- **SEC-036-001:** conservar RBAC, alcance por cliente y CSRF; ningun nombre visible sustituye al ID en
  autorizacion o persistencia.

## Criterios de aceptacion

- Una persona de RR. HH. puede identificar una evaluacion y una postulacion sin interpretar un UUID.
- Los formularios de candidato, lote y exclusiones muestran `codigo · nombre` del cliente.
- Los estados booleanos se expresan con etiquetas como `Pendiente`, `No requerida`, `Activo` o
  `Inactivo`.
- Los filtros no dependen de JavaScript inline.

## Rollback

Revertir campos de presentacion, plantillas y estilos. No existen cambios de esquema o datos.
