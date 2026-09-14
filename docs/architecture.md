# Arquitectura greenfield

TalentIA es un monolito modular bajo `src/talentia`. Dominio no importa frameworks;
aplicacion depende de puertos; infraestructura implementa SQLAlchemy, archivos y lotes; API y
web solo traducen transporte. SQLite usa WAL y Alembic es la unica via de esquema.

El runtime anterior fue retirado del producto mantenido en SPEC-031. Su codigo puede recuperarse
desde el tag `backup/greenfield-before-consolidation-20260914`, pero no comparte ejecucion,
dependencias ni contratos con el runtime oficial.

AG-01, AG-04 y AG-05 son deterministicos. AG-02 y AG-03 se orquestan con LangGraph, validan
estructura y evidencia original y siempre terminan en revision humana. El worker reserva y
confirma antes de ejecutar trabajo externo, por lo que no mantiene transacciones durante IA.

