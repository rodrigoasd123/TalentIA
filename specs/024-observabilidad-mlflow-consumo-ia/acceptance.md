# Aceptación — SPEC-024

## AC-024-001 — Métricas persistentes

**Cubre:** FR-024-001, FR-024-003

```gherkin
Dada una llamada exitosa y una fallida
Cuando se consulta la observabilidad después de reiniciar
Entonces se conservan modelo, tokens, latencia y estado sin doble conteo
```

## AC-024-002 — Privacidad

**Cubre:** SEC-024-001

```gherkin
Dado un prompt con PII y un secreto marcador
Cuando se registra la llamada
Entonces ninguno aparece en parámetros, métricas, tags, trazas ni errores persistidos
```

## AC-024-003 — Frontera API

**Cubre:** FR-024-002, SEC-024-002

```gherkin
Dada la UI de consumo
Cuando carga métricas
Entonces usa FastAPI con autorización y no abre talentia.db directamente
```

## AC-024-004 — Degradación

**Cubre:** NFR-024-001, NFR-024-002

```gherkin
Dado MLflow indisponible y un modelo sin tarifa configurada
Cuando TalentIA procesa una llamada
Entonces el ATS continúa y el costo queda no disponible
```

**Evidencia (2026-09-12):** autologging de contenido retirado; UI sin acceso SQLite; `test_mlflow_observability.py` incluido en suite completa 310 passed.

## Refinamiento R1 aprobado y verificado

### AC-024-005 — Traza navegable por proceso

**Cubre:** FR-024-004, FR-024-005, FR-024-006

```gherkin
Dado un proceso con nodos exitosos, omitidos, reintentados y fallidos
Cuando un administrador abre su detalle
Entonces ve la correlación, topología y secuencia real de nodos con tiempos y estados
```

### AC-024-006 — Tokens y costo por modelo

**Cubre:** FR-024-007

```gherkin
Dadas llamadas de dos modelos con consumos distintos
Cuando se consulta el panel con filtros
Entonces muestra tokens de entrada, salida y total por modelo
Y el costo aparece como no disponible cuando no existe una tarifa aprobada
```

### AC-024-007 — Acceso seguro a MLflow y degradación

**Cubre:** FR-024-008, NFR-024-004, SEC-024-003

```gherkin
Dado MLflow habilitado y una URL confiable entregada por el backend
Cuando el administrador pulsa Abrir MLflow
Entonces se abre el panel configurado en otra pestaña
Pero si MLflow no está disponible TalentIA sigue operativa y el enlace no queda activo
```

### AC-024-008 — Privacidad de trazas jerárquicas

**Cubre:** FR-024-009, SEC-024-004, SEC-024-005

```gherkin
Dado un proceso cuyo documento contiene PII e instrucciones maliciosas
Cuando se persisten y consultan sus runs padre/hijo
Entonces solo aparecen metadatos permitidos y ningún contenido sensible
Y un usuario sin settings:read no puede consultarlos
```
