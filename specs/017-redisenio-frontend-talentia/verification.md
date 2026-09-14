# Verificación — SPEC-017

Estado: VERIFICANDO

Fecha: 2026-09-14

## Evidencia funcional

- Comando: python -m pytest -q tests/greenfield/test_frontend_visual.py tests/greenfield/test_lotes_y_web.py tests/greenfield/test_operational_panels.py tests/greenfield/test_operational_forms.py --basetemp=tmp/pytest-spec-017-focused
  - Resultado: 26 aprobadas, 3 advertencias no bloqueantes.
- Comando: python -m pytest -q --basetemp=tmp/pytest-spec-017-full
  - Resultado: 103 aprobadas, 3 advertencias no bloqueantes, 191.48 s.
- La advertencia de caché pytest se debe a permisos del directorio .pytest_cache; no afecta pruebas ni producto.
- Las advertencias de Starlette y LangGraph provienen de dependencias instaladas y no fueron introducidas por SPEC-017.

## Evidencia estática y seguridad

- Comando: python -m mypy src/talentia
  - Resultado: sin incidencias en 66 archivos.
- Comando: python scripts/check_repository.py
  - Resultado: repositorio seguro, 360 archivos revisados.
- Comando: python -m ruff check tests/greenfield/test_frontend_visual.py
  - Resultado: aprobado.
- Comando: python -m ruff format --check tests/greenfield/test_frontend_visual.py
  - Resultado: aprobado.
- La puerta global de Ruff conserva una incidencia preexistente S110 en la modificación local no perteneciente a esta entrega de src/talentia/web/routes/paginas.py:148. No se modificó trabajo ajeno.

## Revisión visual

- Login inspeccionado en navegador local: composición de dos paneles, foco de acceso, modo manual e identidad correctos.
- Dashboard inspeccionado con sesión real local: navegación activa, hero, tarjetas con datos reales, tabla vacía y acciones correctas.
- Base general inspeccionada: búsqueda, acción primaria, tabla y vacío correctos.
- Formulario de candidato inspeccionado: cuadrícula, etiquetas, inputs y acciones consistentes.
- Los breakpoints de 820 px y 600 px mantienen navegación y sesión visibles y convierten grillas/acciones a una columna.
- Se incluye reducción de movimiento y enlace de salto al contenido.

## Compatibilidad

- No se cambiaron backend, API, base de datos, modelos, servicios, autenticación ni reglas.
- No se añadieron dependencias, recursos remotos, JavaScript ni herramientas de build.
- Se preservaron rutas, nombres de campos, CSRF, HTMX, variables, bucles y condiciones.
- La modificación local preexistente en paginas.py y los Markdown no relacionados permanecen fuera de la entrega.

## Rollback

Revertir los archivos documentales de SPEC-017, aplicacion.css, las cinco plantillas modificadas y test_frontend_visual.py. No hay migraciones ni datos que restaurar.
