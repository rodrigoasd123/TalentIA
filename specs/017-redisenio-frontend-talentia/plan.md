# Plan — SPEC-017

## Inventario confirmado

- Renderizado: FastAPI + Jinja2.
- Estáticos: montaje `/static` desde `src/talentia/web/static`.
- Estilos: Bootstrap local y `css/aplicacion.css`.
- Interactividad: HTMX local; no existe build frontend.
- Layout compartido: `templates/base.html`.
- Páginas: login, inicio, candidatos, módulos operativos, formularios y detalles.

## Secuencia

1. Consolidar tokens y componentes en el CSS existente.
2. Modernizar shell, navegación, cabecera y login conservando contratos.
3. Mejorar dashboard, tablas y vacíos con datos ya presentes.
4. Aplicar componentes a formularios, detalles, evaluación y progreso mediante estilos compatibles.
5. Añadir pruebas estructurales y ejecutar todas las puertas de calidad.

## Dependencias y límites

- Las plantillas dependen del contexto existente; no se agregan consultas.
- Bootstrap y HTMX permanecen locales y sin cambios de versión.
- Ningún cambio puede requerir Node o conexión de red.
- La modificación local preexistente en `paginas.py` se preserva y queda fuera de esta entrega.

## Rollback

Revertir los archivos de SPEC-017. No hay cambios de esquema, datos, configuración ni dependencias.
