# Architecture Decision Records

Un ADR registra una decisión estructural, el contexto en que se tomó y las
consecuencias que se aceptaron. No documenta cómo funciona el sistema —para eso
está el código— sino **por qué es así y no de otra forma**.

Se escribe un ADR cuando una decisión es costosa de revertir, cuando hay
alternativas razonables que se descartaron, o cuando alguien que llegue en seis
meses preguntaría "¿por qué está esto así?".

## Registro

| ADR | Decisión | Estado |
|---|---|---|
| [001](ADR-001-el-agente-propone-el-backend-ejecuta.md) | El agente propone, el backend ejecuta | Aceptada |
| [002](ADR-002-langgraph-con-motor-nativo-de-respaldo.md) | LangGraph con motor nativo de respaldo | Aceptada |
| [003](ADR-003-anonimizacion-antes-de-toda-llamada-al-modelo.md) | La anonimización precede a toda llamada al modelo | Aceptada |
| [004](ADR-004-el-total-lo-calcula-el-backend.md) | El total lo calcula el backend, no el modelo | Aceptada |
| [005](ADR-005-gmail-api-y-secretos-cifrados-en-caliente.md) | Gmail API con OAuth y secretos cifrados en caliente | Aceptada |

## Cómo se relacionan

**ADR-001 es la decisión raíz.** Las demás la desarrollan o la protegen:

- **004** cierra la vía más directa de manipulación: si el modelo no tiene dónde
  escribir una puntuación total ni una acción, el ataque no tiene destino.
- **003** protege la frontera de datos: ninguna llamada al proveedor externo
  transporta información personal.
- **005** aplica el mismo principio a las credenciales y al envío de correo.
- **002** es la elección de herramienta que hace posible que el control del flujo
  esté en el código y no en el modelo.

## Decisiones pendientes de registrar

Cuando se aborden, deberían tener su propio ADR:

- Estrategia de persistencia de la auditoría con cadena de hash y su verificación.
- Modelo de sesiones y rotación de tokens de refresco.
- Elección de motor de búsqueda semántica para el talent pool.
- Estrategia de migración a PostgreSQL y ejecución de la suite contra ambos motores.

## Plantilla

```markdown
# ADR-NNN — Título en forma de decisión

- **Estado:** Propuesta | Aceptada | Sustituida por ADR-XXX
- **Fecha:** AAAA-MM-DD

## Contexto
Qué problema había y qué restricciones aplicaban.

## Decisión
Qué se decidió, en presente y sin ambigüedad.

## Justificación
Por qué esta opción y no las alternativas.

## Consecuencias
Lo bueno y lo malo que se acepta. Las negativas son la parte más útil:
un ADR sin consecuencias negativas normalmente no ha analizado el problema.

## Alternativas descartadas
Qué más se consideró y por qué no.
```
