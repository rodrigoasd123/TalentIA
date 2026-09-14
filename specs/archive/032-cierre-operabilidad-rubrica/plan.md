# Plan — SPEC-032

## Resumen técnico

Se aplicaran cambios pequenos y reversibles sobre el runtime ya verificado: declarar `PYTHONPATH`
en Docker, actualizar las acciones oficiales del workflow, agregar un medidor HTTP con biblioteca
estandar y cubrirlo con pruebas. No se cambia dominio, persistencia, API ni tratamiento de datos.

## Arquitectura y límites afectados

- Despliegue: `Dockerfile`.
- CI: `.github/workflows/ci.yml`.
- Operaciones: `scripts/medir_rendimiento_piloto.py`.
- Calidad: `tests/greenfield/test_cierre_operabilidad.py`.
- Documentacion: README, runbook y estado de cierre.

## Flujo de datos

El medidor recibe solo URL, cantidad, concurrencia y timeout. Cada worker realiza un GET, conserva
codigo de estado y duracion en memoria y descarta el cuerpo. El agregador genera metricas JSON.

## Decisiones y alternativas

- Se usa `urllib.request` y `ThreadPoolExecutor`; se descarta agregar Locust por no justificar una
  dependencia para el piloto.
- Se mide `/health` por defecto; los recorridos con autenticacion se conservan en la UAT.
- No se fija SLA: falta una carga y hardware corporativos representativos.

## Compatibilidad, transición y reversión

No existen cambios de datos o API. Cada archivo puede revertirse de forma independiente. Python
local conserva el mismo comando de arranque.

## Seguridad, privacidad y fallos

No se aceptan cabeceras ni cuerpos configurables y no se registra la respuesta. La URL se limita a
HTTP/HTTPS y cada solicitud tiene timeout. Los errores se agregan por codigo generico.

## Estrategia de pruebas y evidencia

| AC | Tipo | Prueba o evidencia prevista |
|---|---|---|
| AC-032-001 | automatizada | contrato Docker y smoke `talentia.main` |
| AC-032-002 | automatizada | servidor HTTP local, percentiles y JSON |
| AC-032-003 | automatizada/remota | respuesta 500, argumentos invalidos y CI verde |

## Riesgos y mitigaciones

- Variacion temporal: las pruebas validan estructura y orden, no tiempos absolutos.
- Ausencia de Docker local: CI valida el contrato; el build real queda documentado como evidencia
  de entorno pendiente, no como cumplimiento ficticio.

## Aprobación

- [x] Plan aprobado por la persona responsable mediante la instruccion de cierre del 2026-09-14.
