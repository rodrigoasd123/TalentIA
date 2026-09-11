# Criterios de aceptación

- Se puede registrar y editar una ficha con los 18 campos solicitados.
- Un status fuera del catálogo es rechazado con validación 422.
- Una actualización con versión antigua es rechazada.
- La edad calculada prevalece sobre la edad reportada cuando existe fecha de nacimiento.
- El reporte cuenta fuente Adecco, estados entrevistados y descartes explícitos.
- El CSV es un archivo real y no expone campos sensibles.
- La migración funciona en SQLite en ambas direcciones.

