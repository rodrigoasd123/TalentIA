---
id: SPEC-032
titulo: Cierre de operabilidad y evidencia de rubrica
estado: VERIFICADO
responsable_producto: Rodrigo
creado: 2026-09-14
actualizado: 2026-09-14
---

# SPEC-032 — Cierre de operabilidad y evidencia de rubrica

## Problema y resultado esperado

El runtime greenfield cumple el recorrido tecnico del piloto, pero la imagen Docker no declara la
ruta `src`, el workflow usa acciones con runtime obsoleto y no existe un comando acotado para medir
la latencia HTTP del piloto. El cierre debe corregir esas brechas sin habilitar proveedores externos,
OCR pesado ni decisiones corporativas bloqueadas.

## Usuarios y necesidades

- Operaciones necesita un arranque reproducible con Python o Docker.
- Ingenieria necesita CI vigente y una linea base de latencia repetible.
- RR. HH. necesita que los limites humanos y de negocio permanezcan visibles.

## Alcance

### Incluido

- Corregir la resolucion del paquete `src/talentia` dentro de Docker.
- Actualizar las acciones oficiales de CI a runtimes soportados.
- Incorporar una medicion HTTP acotada que reporte solicitudes, errores, p50, p95 y promedio.
- Probar el calculo de metricas, errores y validacion de argumentos sin depender de red externa.
- Reconciliar la documentacion de cierre con el CI y la promocion reales.

### Fuera de alcance

- Resolver `BIZ-001..010`, firmar UAT o validar humanamente el corpus.
- Habilitar Gemini, otro proveedor remoto, OCR adicional o tratamiento de CV reales.
- Introducir Node.js, infraestructura distribuida o nuevas dependencias de runtime.

## Requisitos funcionales

- **FR-032-001:** La imagen Docker debe poder importar `talentia.main:app` desde el layout `src`.
- **FR-032-002:** Debe existir un comando que mida un endpoint HTTP configurable y emita JSON con
  cantidad total, exitos, errores, promedio, p50 y p95 en milisegundos.
- **FR-032-003:** La medicion debe devolver un codigo distinto de cero cuando existan errores HTTP o
  de conexion, sin imprimir cuerpos ni datos personales.

## Requisitos no funcionales

- **NFR-032-001:** El piloto debe continuar ejecutandose solo con Python; Node.js no sera requisito.
- **NFR-032-002:** La medicion debe ser acotada por cantidad, concurrencia y timeout configurables.
- **NFR-032-003:** El CI debe usar versiones oficiales basadas en Node.js 24 y conservar todas sus
  puertas actuales.

## Seguridad y privacidad

- **SEC-032-001:** La medicion no debe persistir ni mostrar cuerpos, cabeceras, cookies o PII.
- **SEC-032-002:** No se incorporaran secretos, CV, bases de datos ni llamadas a proveedores.

## Reglas y fuentes de verdad

- `docs/sdd/constitucion.md` y SPEC-030/031 gobiernan el alcance.
- Las decisiones `BIZ-001..010` permanecen cerradas y con fallo seguro.

## Supuestos confirmados

- El usuario aprobo completar todas las brechas tecnicas implementables de la rubrica.
- La computadora del piloto dispone de Python; Docker es una opcion de empaquetado.

## Riesgos y fallos esperados

- Un presupuesto rigido de latencia seria fragil entre equipos; el script mide y reporta, pero no
  inventa un SLA corporativo.
- Docker no esta disponible en el equipo actual; se agrega prueba estatica y smoke de importacion.

## Preguntas abiertas

Ninguna bloqueante dentro del alcance tecnico.

## Historial de decisiones

| Fecha | Decision | Responsable | Motivo |
|---|---|---|---|
| 2026-09-14 | Limitar el cierre a brechas tecnicas sin decisiones BIZ | Rodrigo | Autorizacion explicita de cierre |
