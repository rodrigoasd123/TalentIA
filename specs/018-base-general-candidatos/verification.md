# Verificación

- `pytest tests/ats/test_candidate_general_database.py -q`: 4 pruebas superadas.
- Suite completa: 271 pruebas superadas.
- `alembic downgrade a94109cb367c` y `alembic upgrade head`: correctos sobre SQLite.
- `python -m compileall -q app ats_frontend`: correcto.
