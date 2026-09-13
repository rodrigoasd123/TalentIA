# Pull request preparado - fase 8

## Titulo

`feat: completar reconstruccion greenfield gobernada de TalentIA`

## Destino

- Base: `main`
- Rama: `codex/rubrica-greenfield-talentia`
- Estado: listo para revision; merge bloqueado hasta autorizacion expresa.

## Resumen

- Incorpora el monolito modular FastAPI/Jinja2/HTMX con SQLite y Alembic.
- Completa candidatos, perfiles, postulaciones, documentos, evaluacion con evidencia, revision
  humana, trabajos durables, lotes, ex-TCS, exclusiones y metricas sanitizadas.
- Implementa AG-01/04/05 deterministas y AG-02/03 gobernados con fallback humano.
- Agrega instalacion Windows, migraciones reversibles, backup/restauracion, CI y evidencia SDD.

## Verificacion adjunta

- Fase 7: 81 pruebas greenfield y 391 totales; 2 advertencias conocidas; controles estaticos y
  escaner aprobados.
- Instalacion limpia: `pip check` e import de `talentia.main:app` aprobados; 9 pruebas de smoke.
- UAT tecnica: 23 escenarios automatizados aprobados con datos sinteticos.
- Migraciones: upgrade/downgrade por revision y retorno a `head` aprobados.
- Backup/restauracion: integridad SQLite y no sobreescritura aprobadas.

## Riesgos y limites

- `BIZ-001..010` estan fuera del alcance y mantienen comportamiento conservador.
- La aceptacion humana de RR. HH. esta pendiente y debe registrarse antes del merge.
- SQLite es solo para piloto local; no se propone despliegue productivo compartido.
- Dos advertencias de deprecacion requieren una actualizacion posterior controlada.

## Revision solicitada

Validar seguridad, privacidad, recorrido operativo y decisiones fuera de alcance. No hacer merge
hasta contar con aceptacion funcional y autorizacion expresa del propietario.
