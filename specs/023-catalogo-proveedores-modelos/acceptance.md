# Aceptación — SPEC-023

## AC-023-001 — Modelo real

**Cubre:** FR-023-001, FR-023-002

```gherkin
Dado un modelo habilitado
Cuando se genera una respuesta
Entonces se invoca exactamente ese modelo y se devuelve su procedencia real
```

## AC-023-002 — Credenciales aisladas

**Cubre:** FR-023-003, SEC-023-001

```gherkin
Dadas claves distintas por proveedor
Cuando cambia el modelo
Entonces solo se entrega al adaptador su clave y nunca se expone
```

## AC-023-003 — Autorización

**Cubre:** FR-023-004, SEC-023-002

```gherkin
Dado un usuario sin settings:write
Cuando intenta probar o cambiar credenciales
Entonces la API rechaza la operación sin revelar secretos
```

## AC-023-004 — Instalación y fallback

**Cubre:** NFR-023-001, NFR-023-002

```gherkin
Dado un entorno sin credenciales
Cuando se instala e inicia TalentIA
Entonces las importaciones funcionan y el ATS determinista sigue disponible
```

**Evidencia (2026-09-12):** instalación editable completada; suite completa 310 passed; catálogo, fábrica, credenciales cifradas y fallback cubiertos por pruebas existentes y compilación.

## Refinamiento R1 aprobado y verificado

### AC-023-005 — Alta segura de proveedor y modelo

**Cubre:** FR-023-005, FR-023-006, SEC-023-004, SEC-023-005

```gherkin
Dado un administrador con settings:write
Cuando registra un proveedor OpenAI-compatible y uno de sus modelos
Entonces se persisten sus metadatos y el secreto cifrado
Y ninguna respuesta, log, auditoría o traza expone la credencial
```

### AC-023-006 — RBAC, CSRF y concurrencia

**Cubre:** SEC-023-003, SEC-023-006

```gherkin
Dado un usuario sin settings:write, un CSRF inválido o una versión obsoleta
Cuando intenta mutar el catálogo o las asignaciones
Entonces la operación completa se rechaza sin cambios parciales
```

### AC-023-007 — Deshabilitación compatible

**Cubre:** FR-023-007, FR-023-008, FR-023-009, NFR-023-004

```gherkin
Dado un modelo activo o referenciado por resultados históricos
Cuando el administrador intenta deshabilitarlo
Entonces TalentIA exige primero una asignación válida o aplica el fallback aprobado
Y conserva intacta la procedencia histórica
```

### AC-023-008 — Migración y rollback SQLite

**Cubre:** NFR-023-003, FR-023-009

```gherkin
Dada una instalación con configuración del catálogo estático
Cuando se aplica y revierte la migración R1
Entonces la configuración vigente sigue siendo utilizable y no se pierden secretos
```
