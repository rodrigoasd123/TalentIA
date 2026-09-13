# Seguridad greenfield

- Contrasenas con `scrypt` y sal aleatoria.
- Sesiones HMAC con vencimiento, cookie `HttpOnly`, `SameSite=Strict` y CSRF web.
- RBAC y alcance por cliente en casos de uso; la API no confia en IDs del cliente.
- CSP, anti-framing, `nosniff` y politica de referencia.
- PDF/DOCX validados por MIME, firma y tamano; almacenamiento no publico.
- Sanitizacion de PII cerrada y deteccion de instrucciones incrustadas antes de IA.
- Auditoria encadenada sin contrasenas, CV ni PII completa.
- BGC, Equifax, retencion y transiciones sensibles bloqueados por decisiones BIZ pendientes.

