# SPEC-035 - Identidad visual corporativa TCS

- **Estado:** VERIFIED
- **Fuente:** Solicitud del propietario del 2026-09-14.

## Problema

Las vistas incorporadas recientemente mezclaron colores y componentes sin una identidad uniforme. La
aplicacion debe volver a comunicar la pertenencia a TCS sin alterar sus flujos operativos.

## Requisitos

- **FR-035-001:** usar una marca TCS local y escalable basada en la referencia, sin incrustar las
  imagenes de referencia ni sus fondos.
- **FR-035-002:** mantener la paleta azul y cian de TalentIA, centralizada en los tokens CSS existentes.
- **FR-035-003:** conservar estados semanticos de exito, advertencia y error por accesibilidad.
- **NFR-035-001:** no incorporar recursos visuales remotos ni un runtime adicional.
- **NFR-035-002:** conservar navegacion, rutas, formularios, responsive y contratos HTMX existentes.

## Criterios de aceptacion

- El logotipo local TCS aparece con texto alternativo en login y shell autenticado.
- Los componentes primarios mantienen la identidad azul y cian desde el sistema visual central.
- Las pruebas de contratos visuales, seguridad y formularios continuan aprobadas.

## Rollback

Revertir las referencias al activo y los tokens de identidad. No existen cambios de datos ni esquema.
