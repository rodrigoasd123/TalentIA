# Verificación — SPEC-004

## Entorno

- Fecha: 2026-09-10
- Revisión/commit: `239ceb60b5c0d80b7f3ca67c8da69f67857ab35b` publicado en `rodrigoasd123/TalentIA`
- Plataforma: Windows, Python 3.13.7, SQLite, proveedor LLM simulado

## Evidencia por criterio

| AC | Requisitos | Evidencia | Resultado |
|---|---|---|---|
| AC-001 | FR-001–FR-005, SEC-004 | `tests/ats/test_intake_api.py` | APROBADO |
| AC-002 | FR-004, NFR-008, SEC-004 | `tests/ats/test_ocr_adapter.py` | APROBADO |
| AC-003 | FR-006–FR-008, SEC-005–SEC-007 | pruebas de dominio, grafo y evidencia | APROBADO |
| AC-004 | FR-006, FR-007, SEC-005, SEC-007, SEC-008 | `tests/ats/test_prompt_injection.py` | APROBADO |
| AC-005 | FR-006, SEC-003, SEC-006 | `tests/ats/test_pii_leakage.py` | APROBADO |
| AC-006 | FR-009, FR-011, SEC-002, SEC-008 | flujo de revisión, estados y seguridad | APROBADO |
| AC-007 | FR-010, FR-015, SEC-002, SEC-003 | Candidate 360, persistencia y auditoría | APROBADO |
| AC-008 | FR-012 | pruebas de ranking y comparación contextual | APROBADO |
| AC-009 | FR-013, SEC-007, SEC-008 | prueba `test_sourcing_solo_devuelve...` | APROBADO |
| AC-010 | FR-014, SEC-008, SEC-009 | pruebas de correo, políticas y `DRY_RUN` | APROBADO |
| AC-011 | FR-016, NFR-003, NFR-004, NFR-006 | seed reproducible, API/UI smoke, suite sin red | APROBADO |
| AC-012 | FR-017, NFR-007, NFR-008 | 41 pruebas heredadas dentro de la regresión | APROBADO |
| AC-013 | SEC-001, SEC-010, SEC-011 | escáner aprobado y SHA remoto `239ceb60b5c0d80b7f3ca67c8da69f67857ab35b` confirmado | APROBADO |

## Comandos ejecutados

| Comando | Resultado | Observaciones |
|---|---|---|
| `python scripts/seed.py --reset` | APROBADO | 5 usuarios, 4 vacantes, 9 candidatos, 9 CV, 10 candidaturas ficticias |
| `python -m pytest -q --basetemp .pytest-tmp` | APROBADO | 256 pruebas; una advertencia de deprecación externa TestClient/httpx |
| `python scripts/check_repository.py` | APROBADO | 214 archivos revisados, sin secreto ni artefacto prohibido |
| Smoke API 8010 + Streamlit 8510 | APROBADO | `api_ready=True`, `ui_ready=True`; procesos detenidos |

## Hallazgos

| Severidad | Ubicación | Problema | Acción |
|---|---|---|---|
| MENOR | dependencia externa | TestClient informa deprecación de compatibilidad con httpx | Vigilar actualización; no afecta ejecución ni pruebas |
| INFORMATIVO | laboratorio | SQLite, sesión recruiter local y datos persistidos sin cifrado integral | Uso limitado a localhost y datos ficticios |

## Limitaciones conocidas

- No hay LinkedIn RSC, scraping ni automatización: la consulta Boolean se ejecuta manualmente.
- Gmail permanece en borrador y `DRY_RUN`; no se verificó OAuth ni envío real.
- No se validó PostgreSQL, multiempresa ni un despliegue público con CV reales.
- La comprobación visual fue una prueba de salud del servidor Streamlit, no una matriz completa de navegadores.

## Veredicto

- [x] VERIFICADO
- [ ] REQUIERE CORRECCIONES
- [ ] NO VERIFICABLE
