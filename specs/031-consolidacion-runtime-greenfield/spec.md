---
id: SPEC-031
titulo: Consolidacion del runtime greenfield
estado: VERIFICANDO
responsable_producto: Rodrigo
creado: 2026-09-14
actualizado: 2026-09-14
---

# SPEC-031 — Consolidacion del runtime greenfield

## Problema y resultado esperado

TalentIA mantiene dos aplicaciones ejecutables y dependencias contradictorias. El resultado es un
unico producto mantenido bajo `src/talentia`, ejecutable con Python 3.12, FastAPI, Jinja2 y HTMX.

## Usuarios y necesidades

- Operacion del piloto: instalacion y arranque inequívocos sin Node.js ni Streamlit.
- Desarrollo: una sola suite, migracion, paquete y CI oficiales.

## Alcance

### Incluido

- Inventario KEEP/MIGRATE/REMOVE de los runtimes existentes.
- Retiro versionado de `app`, `ats_frontend`, `frontend`, `backend`, `agente_postulacion`, sus
  pruebas, migraciones y scripts exclusivos.
- Normalizacion de paquete, dependencias, Docker, CI, documentacion y scripts.
- Conservacion de fixtures utiles, specs y ADR como evidencia historica.

### Fuera de alcance

- Borrar ramas remotas, bases locales no versionadas o documentos reales.
- Corregir en esta spec todas las brechas funcionales de la rubrica.

## Requisitos funcionales

- **FR-001:** El repositorio debe exponer `talentia.main:app` como unico entrypoint web oficial.
- **FR-002:** Ningun archivo mantenido debe importar los paquetes heredados.
- **FR-003:** La instalacion del piloto no debe instalar Streamlit, FAISS, OCR heredado ni MLflow.
- **FR-004:** Las migraciones y datos greenfield deben conservarse sin perdida.

## Requisitos no funcionales

- **NFR-001:** El runtime debe instalarse y ejecutarse con Python 3.12.
- **NFR-002:** CI debe comprobar Ruff, formato, mypy, migracion y pruebas del arbol mantenido.
- **NFR-003:** El retiro debe ser reversible mediante el tag de respaldo registrado.

## Seguridad y privacidad

- **SEC-001:** No se versionaran ni eliminaran secretos, bases locales, CV ni almacenamiento local.
- **SEC-002:** La imagen del piloto no debe iniciar servicios heredados o telemetria externa.

## Reglas y fuentes de verdad

- Fuente inicial: commit `4b33cd83cc42bd9fe0caaf4b66679cb926aca907`.
- Respaldo: tag `backup/greenfield-before-consolidation-20260914`.
- Aplicacion oficial: `src/talentia` y `migrations_greenfield`.

## Supuestos confirmados

- El encargo del 2026-09-14 aprueba alcance, plan y retirada del legado con conservacion de historial.
- Las specs antiguas se mantienen como registro; no son runtime.

## Riesgos y fallos esperados

- Una referencia documental puede quedar obsoleta; se detectara con busqueda global.
- Una dependencia compartida puede retirarse por error; import, migracion y suite lo detectaran.

## Preguntas abiertas

Ninguna bloqueante.

## Historial de decisiones

| Fecha | Decision | Responsable | Motivo |
|---|---|---|---|
| 2026-09-14 | Greenfield sera la unica linea oficial | Rodrigo | Encargo explicito |
| 2026-09-14 | Conservar specs/ADR historicos | Ingenieria | Trazabilidad y rollback |
