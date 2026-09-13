# Tareas - SPEC-030

- [x] **T-030-001** Bootstrap, CI y configuracion segura. `[IMP-001..003]`
- [ ] **T-030-002** Dominio puro y politicas bloqueadas. `[IMP-004..009]` Parcial:
  dominio implementado; cierre bloqueado por `BIZ-001..005`, `BIZ-008..010`.
- [ ] **T-030-003** Persistencia, migraciones y unidad de trabajo. `[IMP-010..013]` Parcial:
  esquema reversible, UoW, auditoria y locking implementados; falta fusion automatica de cambios
  disjuntos de `IMP-012`.
- [ ] **T-030-004** Casos de uso, seguridad y API. `[IMP-014..019]` Parcial: contratos P0,
  RBAC y scope implementados; cierres de lotes/exclusiones dependen de `BIZ-001/008`.
- [ ] **T-030-005** Agentes, jobs y workflow. `[IMP-020..026]` Parcial: agentes
  deterministicos, guardrails, jobs, checkpoints y grafo implementados; veredicto final bloqueado por
  `BIZ-005`.
- [ ] **T-030-006** Web Jinja2/HTMX y flujos operativos. `[IMP-027..029]` Parcial: shell,
  sesion, navegacion y base general implementados; pantallas operativas restantes no estan cerradas.
- [ ] **T-030-007** Privacidad, auditoria y corpus de pruebas. `[IMP-030..032]` Parcial:
  guardrails, auditoria encadenada y corpus golden implementados; retencion depende de `BIZ-007/010`.
- [ ] **T-030-008** Observabilidad, metricas y operacion. `[IMP-033..035]` Parcial: correlacion,
  metricas, scripts y runbook implementados; baseline de CV util depende de `BIZ-006`.
