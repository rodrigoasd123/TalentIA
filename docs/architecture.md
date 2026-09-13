# Arquitectura greenfield

TalentIA es un monolito modular bajo `src/talentia`. Dominio no importa frameworks;
aplicacion depende de puertos; infraestructura implementa SQLAlchemy, archivos y lotes; API y
web solo traducen transporte. SQLite usa WAL y Alembic es la unica via de esquema.

El runtime anterior permanece como rollback temporal. No comparte base ni contratos con el
nuevo runtime. La migracion de datos se mantiene bloqueada por `BIZ-007`, `BIZ-008` y
`BIZ-010`.

AG-01, AG-04 y AG-05 son deterministicos. AG-02 y AG-03 se orquestan con LangGraph, validan
estructura y evidencia original y siempre terminan en revision humana. El worker reserva y
confirma antes de ejecutar trabajo externo, por lo que no mantiene transacciones durante IA.

