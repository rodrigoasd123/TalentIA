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
