# Decisiones de negocio - fase 8

Fecha de refinamiento: 2026-09-13

## Acuerdo de alcance

No se recibieron valores ni aprobaciones corporativas para `BIZ-001..010`. Por lo tanto, las diez
decisiones quedan **explicitamente fuera del alcance de este piloto**. Esta clasificacion satisface
el criterio de no inventar reglas y no equivale a una decision de negocio de TCS.

| ID | Estado de fase 8 | Comportamiento conservador vigente | Refinamiento necesario para incorporarla |
|---|---|---|---|
| BIZ-001 | Fuera de alcance | No se calcula vigencia por motivo de rechazo | Motivos, plazos, excepciones y responsable |
| BIZ-002 | Fuera de alcance | No se reabre `NO APTO` sin una regla aprobada | Condiciones, roles y auditoria requerida |
| BIZ-003 | Fuera de alcance | No se revierte `BLACKLIST` | Rol, doble control y justificacion |
| BIZ-004 | Fuera de alcance | La similitud de nombres solo deriva a revision | Umbral, normalizacion y tratamiento de falsos positivos |
| BIZ-005 | Fuera de alcance | Evidencia ausente conserva la candidatura y solicita revision | Resultado permitido por tipo de requisito |
| BIZ-006 | Fuera de alcance | `cv_util` permanece nulo y marcado como bloqueado | Definicion, denominador y ventana temporal |
| BIZ-007 | Fuera de alcance | No existe eliminacion automatica | Plazos, base legal, excepciones y borrado verificable |
| BIZ-008 | Fuera de alcance | No se fusionan identidades dudosas entre clientes | Alcance de unicidad y gobierno de conflictos |
| BIZ-009 | Fuera de alcance | No se infiere un mapeo adicional de estados | Tabla oficial de estados y transiciones |
| BIZ-010 | Fuera de alcance | Se bloquea el almacenamiento de BGC y Equifax | Campos, cifrado, acceso, retencion y auditoria |

## Regla para un cambio futuro

Cada decision requiere aprobacion expresa de TCS, refinamiento de `spec.md`, plan aprobado, criterios
de aceptacion y pruebas antes de modificar codigo. Mientras tanto se conserva el fallo cerrado y la
revision humana ya verificados.
