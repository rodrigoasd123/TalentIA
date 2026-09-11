# SPEC-019 — Tareas

## Estado

**Implementación completada.** La evidencia reproducible se conserva en
`verification.md`.

## T0 — Coordinación y línea base

- [x] T0.1 Actualizar referencias remotas y comprobar que SPEC-019 sigue libre.
- [x] T0.2 Registrar commit base, estado del árbol y archivos de la rama paralela.
- [x] T0.3 Ejecutar regresión, smoke y escáner como línea base.
- [x] T0.4 Crear inventario automatizado de nombres heredados y allowlist justificada.
- [x] T0.5 Detenerse y coordinar si aparece colisión o fallo base reproducible.

## T1 — Configuración oficial TalentIA

- [x] T1.1 Implementar resolución oficial `TALENTIA_*` para todos los campos estáticos.
- [x] T1.2 Implementar fallback temporal a cada alias `VERA_*`.
- [x] T1.3 Garantizar prioridad TalentIA y advertencias sin valores.
- [x] T1.4 Migrar el archivo de clave de desarrollo con detección segura de conflicto.
- [x] T1.5 Conservar compatibilidad criptográfica con secretos persistidos.
- [x] T1.6 Emitir nuevos JWT con identidad TalentIA y aceptar temporalmente el emisor
  heredado sin extender expiraciones.
- [x] T1.7 Actualizar `.env.example`, Docker, CI y cliente API a nombres oficiales.
- [x] T1.8 Añadir pruebas exhaustivas de precedencia, aliases, secretos y advertencias.

## T2 — Base SQLite `talentia.db`

- [x] T2.1 Implementar inspector de SQLite en modo lectura.
- [x] T2.2 Implementar hash, revisión Alembic, integridad y conteos críticos.
- [x] T2.3 Implementar adopción por copia temporal verificada y promoción atómica.
- [x] T2.4 Crear respaldo y manifiesto sin PII ni secretos.
- [x] T2.5 Bloquear de forma segura la presencia simultánea de ambas bases.
- [x] T2.6 Respetar URLs configuradas explícitamente sin moverlas.
- [x] T2.7 Implementar reversión que no sobrescriba destinos existentes.
- [x] T2.8 Integrar la adopción antes de crear el motor SQLAlchemy.
- [x] T2.9 Probar instalación nueva, origen heredado, destino existente, conflicto,
  fallos inyectados y reintento idempotente.
- [x] T2.10 Probar Alembic hasta `head` sin modificar revisiones publicadas.

## T3 — Identidad visible

- [x] T3.1 Renombrar metadatos y mensajes activos de FastAPI a TalentIA.
- [x] T3.2 Renombrar ayudas, errores, demo y datos ficticios visibles.
- [x] T3.3 Actualizar nombre público del paquete si el análisis confirma compatibilidad.
- [x] T3.4 Actualizar documentación vigente sin reescribir historia ni ADR.
- [x] T3.5 Añadir prueba automatizada de referencias visibles y allowlist histórica.

## T4 — Analizador documental interno

- [x] T4.1 Inventariar contratos y elegir implementación canónica por capacidad.
- [x] T4.2 Crear adaptador de aplicación para PDF y OCR existentes.
- [x] T4.3 Integrar filtros y ranking documental sin duplicación.
- [x] T4.4 Integrar embeddings, caché vectorial y caché de respuestas existentes.
- [x] T4.5 Integrar consulta RAG con evidencia y guardrails.
- [x] T4.6 Exponer contratos FastAPI tipados con RBAC y límites.
- [x] T4.7 Crear página Streamlit interna que consuma exclusivamente la API.
- [x] T4.8 Retirar navegación e instrucciones al frontend separado.
- [x] T4.9 Documentar rollback técnico temporal no visible.
- [x] T4.10 Ejecutar regresión PDF, OCR, ranking, embeddings, cachés y RAG.

## T5 — Candidatos y fuente de verdad

- [x] T5.1 Eliminar usos decisorios o métricos de `Candidate.candidate_status`.
- [x] T5.2 Conservar columna y valores anteriores para trazabilidad.
- [x] T5.3 Mostrar estados por postulación y vacante en la ficha general.
- [x] T5.4 Señalar múltiples postulaciones sin colapsar estados automáticamente.
- [x] T5.5 Confirmar SQL como fuente posterior a importación CSV/XLSX.
- [x] T5.6 Verificar auditoría, versiones y duplicados conservadores.

## T6 — Seguridad, documentación y operación

- [x] T6.1 Verificar denegación por defecto y RBAC de nuevas rutas.
- [x] T6.2 Verificar ausencia de PII y secretos en logs, errores y manifiestos.
- [x] T6.3 Documentar instalación, migración, conflicto, diagnóstico y reversión.
- [x] T6.4 Documentar aliases, obsolescencia y criterio de retiro.
- [x] T6.5 Documentar brechas de cifrado PII, retención, eliminación y backups.
- [x] T6.6 Actualizar catálogo y mapa SDD al completar la implementación.

## T7 — Verificación y cierre

- [x] T7.1 Ejecutar la suite completa del ATS.
- [x] T7.2 Ejecutar la suite completa del analizador documental.
- [x] T7.3 Ejecutar pruebas de migración y reversión SQLite.
- [x] T7.4 Ejecutar smoke de FastAPI y Streamlit.
- [x] T7.5 Ejecutar escáner de secretos, PII y artefactos prohibidos.
- [x] T7.6 Verificar visualmente identidad TalentIA en superficies principales.
- [x] T7.7 Comparar el diff con la rama paralela y confirmar ausencia de sobrescritura.
- [x] T7.8 Crear `verification.md` con comandos, resultados y limitaciones reales.
- [x] T7.9 Crear commits descriptivos separados sin publicar.
- [x] T7.10 Solicitar autorización explícita antes de cualquier push a GitHub.
