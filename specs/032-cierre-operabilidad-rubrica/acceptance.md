# Criterios de aceptación — SPEC-032

**Característica:** cierre técnico y operativo del piloto.

## AC-032-001 — Runtime Docker importable

**Cubre:** FR-032-001, NFR-032-001

```gherkin
Escenario: resolver el paquete greenfield dentro de la imagen
  Dado el Dockerfile oficial con layout src
  Cuando se inicia talentia.main:app
  Entonces Python puede resolver el paquete sin depender del directorio heredado
```

**Evidencia requerida:** prueba automatizada del contrato Docker y smoke de importación.

## AC-032-002 — Medición reproducible y minimizada

**Cubre:** FR-032-002, NFR-032-002, SEC-032-001

```gherkin
Escenario: medir un endpoint saludable
  Dado un endpoint HTTP local
  Cuando se ejecuta una cantidad acotada de solicitudes
  Entonces se emite JSON con conteos y latencias p50 y p95 sin cuerpos ni cabeceras
```

**Evidencia requerida:** pruebas unitarias y de servidor local.

## AC-032-003 — Fallo visible y CI vigente

**Cubre:** FR-032-003, NFR-032-003, SEC-032-002

```gherkin
Escenario: detectar solicitudes fallidas
  Dado un endpoint que responde con error
  Cuando se ejecuta la medición
  Entonces el resultado contabiliza los errores y el comando falla de forma segura
```

**Evidencia requerida:** prueba automatizada y workflow remoto verde.
