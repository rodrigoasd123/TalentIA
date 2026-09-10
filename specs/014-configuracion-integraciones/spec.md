---
id: SPEC-014
titulo: Configuración e integraciones
estado: VERIFICADO
tipo: VISTA_DERIVADA
origen: SPEC-004
actualizado: 2026-09-10
---

# SPEC-014 — Configuración e integraciones

## Propósito

Administrar parámetros y comprobar proveedores sin revelar secretos ni convertir una integración opcional en dependencia del flujo local.

## Alcance vigente

- Catálogo de configuración con propósito documentado.
- Secretos cifrados y respuestas enmascaradas.
- Estado y prueba de proveedor LLM; adaptador simulado predeterminado.
- Estado de correo y feature flags conservadores.
- Límites de documentos/importación configurables.
- Salud de API y métricas protegidas.

## Fuera de alcance

Gestor corporativo de secretos, OAuth Gmail completo, LinkedIn API, LangSmith/MLflow operativo y configuración productiva multiempresa.

## Requisitos heredados

- **FR-014-001 (SPEC-004 FR-016):** recorrido local sin API key mediante adaptador simulado.
- **FR-014-002 (SPEC-004 SEC-009):** cifrar secretos y no devolverlos completos.
- **FR-014-003:** solo un actor autorizado modifica configuración; claves desconocidas se rechazan o ignoran de forma segura.

## Implementación y evidencia

`app/core/config.py`, `settings_store.py`, factory/adaptadores LLM, rutas `/config/*`, página `1_Configuracion.py` y pruebas `test_config_and_graph.py`, `test_security_endpoints.py`.

## Historial

- 2026-09-10: extraída de SPEC-004 como vista funcional, sin cambio de comportamiento.
