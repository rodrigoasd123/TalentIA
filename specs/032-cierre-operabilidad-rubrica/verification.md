# Evidencia de implementación — SPEC-032

## Estado

`VERIFICANDO`: las tareas técnicas y sus pruebas están completas. El cierre formal corresponde a
la revisión SDD posterior y no sustituye la UAT ni las aprobaciones corporativas.

## Trazabilidad

| Criterio | Evidencia | Resultado |
|---|---|---|
| AC-032-001 | `Dockerfile`, `.github/workflows/ci.yml`, pruebas de contrato | Cumple |
| AC-032-002 | `scripts/medir_rendimiento_piloto.py`, servidor HTTP local en pruebas | Cumple |
| AC-032-003 | Validaciones de esquema, límites, timeout y errores HTTP | Cumple |

## Verificaciones ejecutadas

- Suite completa: `98 passed`.
- Ruff: comprobación y formato correctos en 93 archivos.
- mypy: sin errores en 66 archivos fuente.
- Dependencias: `pip check` sin conflictos.
- Escáner del repositorio: 353 archivos revisados sin hallazgos.
- Identidad del producto: `TalentIA`.
- Migraciones: Alembic aplicó `0001` a `0004` sobre una base desechable.
- Importación: `talentia` carga correctamente con `PYTHONPATH=src`.
- Prueba HTTP local: 20 solicitudes, concurrencia 4, 20 éxitos, 0 errores,
  promedio 23.732 ms, p50 4.459 ms y p95 95.461 ms.

## Revisión de seguridad

- El medidor solo acepta HTTP/HTTPS, aplica límites de carga y timeout.
- No persiste ni muestra cuerpos, cabeceras, cookies o secretos de las respuestas.
- No se añadieron proveedores remotos, credenciales ni dependencias nuevas.
- `.dockerignore` excluye secretos, bases locales, almacenamiento y cachés.

## Limitaciones y evidencia externa pendiente

- Docker no está instalado en la estación de verificación; el contrato se cubrió con pruebas, pero
  falta ejecutar el build real si Docker formará parte del piloto.
- Persisten dos advertencias no bloqueantes de dependencias existentes: Starlette/AnyIO y
  serialización de checkpoints de LangGraph.
- La línea base local no representa carga productiva ni constituye un SLA.
- UAT de RR. HH., decisiones `BIZ-*`, validación humana del benchmark y aprobación corporativa de
  despliegue requieren responsables humanos y no pueden ser declaradas por ingeniería.
