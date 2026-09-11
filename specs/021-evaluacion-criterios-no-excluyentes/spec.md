# SPEC-021 — Criterios no excluyentes y penalización configurable

## Metadatos

- **ID:** SPEC-021
- **Estado:** VERIFICANDO
- **Fecha:** 2026-09-11
- **Responsable de aprobación:** responsable de producto

## Problema

TalentIA trata actualmente todo filtro obligatorio incumplido o no acreditado como excluyente. El grafo omite la evaluación semántica y muestra una puntuación de cero aunque el CV acredite otros requisitos. Esto confunde a RR. HH. y equipara indebidamente la ausencia de evidencia con un incumplimiento comprobado.

## Usuarios

- Personal de RR. HH. que configura criterios de una vacante.
- Revisores humanos que interpretan la evaluación documental.
- Candidatos afectados por una recomendación asistida.

## Alcance

- Permitir que cada criterio de una vacante sea `excluyente` o `ponderado`.
- Configurar para criterios ponderados un peso o penalización dentro del puntaje total.
- Distinguir los estados `cumple`, `no cumple` y `no acreditado`.
- Continuar la evaluación semántica cuando falle o no se acredite un criterio ponderado.
- Mostrar puntaje calculado, cobertura de requisitos y bloqueantes como conceptos separados.
- Enviar a revisión humana los criterios requeridos que no estén acreditados.
- Versionar y volver a aprobar una vacante cuando cambie esta política.

## Fuera de alcance

- Eliminar los filtros excluyentes legítimos.
- Permitir que Gemini decida pesos, penalizaciones o carácter excluyente.
- Rechazar o cambiar automáticamente el estado de una candidatura.
- Aplicar retroactivamente cambios a evaluaciones históricas inmutables.
- Definir una política corporativa universal para todos los idiomas o vacantes.

## Supuestos y decisiones propuestas

- La configuración pertenece a la versión aprobada de cada vacante.
- El idioma será ponderado por defecto; RR. HH. podrá marcarlo excluyente de forma explícita.
- `No acreditado` significa que el CV no contiene evidencia suficiente y no equivale a `no cumple`.
- Un criterio ponderado no cortocircuita el grafo. Su efecto numérico será determinístico y auditable.
- La suma de pesos seguirá validándose en el backend.
- Toda ausencia de evidencia en un criterio requerido generará revisión humana, aunque no anule el puntaje.

## Requisitos funcionales

- **FR-021-001:** El sistema debe permitir configurar cada criterio como `excluyente` o `ponderado` dentro de una versión de vacante.
- **FR-021-002:** El sistema debe exigir para cada criterio ponderado una penalización o peso válido, visible antes de aprobar la vacante.
- **FR-021-003:** El evaluador debe clasificar cada resultado como `cumple`, `no_cumple` o `no_acreditado`, conservando evidencia y explicación.
- **FR-021-004:** Solo un criterio excluyente con estado `no_cumple` debe poder cortar la evaluación semántica; un resultado `no_acreditado` debe pasar a revisión humana.
- **FR-021-005:** Un criterio ponderado incumplido o no acreditado debe reducir el puntaje según la configuración, sin forzar por sí solo un total de cero.
- **FR-021-006:** La API y la interfaz deben presentar por separado el puntaje, la cobertura de criterios, los bloqueantes y los motivos de revisión.
- **FR-021-007:** Editar tipo, peso, penalización o nivel requerido debe crear una nueva versión de criterios e invalidar la aprobación vigente de la vacante.
- **FR-021-008:** Las evaluaciones históricas deben conservar la versión de criterios y el cálculo original; una reevaluación debe crear un resultado nuevo.

## Requisitos no funcionales

- **NFR-021-001:** El cálculo de penalizaciones debe ser determinístico, reproducible y ejecutarse en el backend.
- **NFR-021-002:** Los resultados deben explicar el valor esperado, el valor observado, la evidencia y el impacto numérico de cada criterio.
- **NFR-021-003:** La modificación debe conservar compatibilidad con vacantes existentes mediante una migración explícita y reversible.
- **NFR-021-004:** La interfaz no debe mostrar `0%` cuando la evaluación no se haya ejecutado; debe mostrar `No calculada` y el motivo.

## Seguridad, equidad y gobierno

- **SEC-021-001:** El LLM no debe decidir si un criterio es excluyente ni calcular la penalización final.
- **SEC-021-002:** La ausencia de una declaración en el CV no debe convertirse automáticamente en incumplimiento comprobado.
- **SEC-021-003:** Todo resultado `no_acreditado` de un criterio requerido debe impedir una decisión automática y solicitar revisión humana.
- **SEC-021-004:** Los cambios de política de una vacante deben exigir permisos, aprobación humana y auditoría sin sobrescribir evaluaciones anteriores.
- **SEC-021-005:** La configuración no debe permitir criterios relativos a atributos sensibles o protegidos.

## Compatibilidad y migración propuesta

- Las vacantes existentes conservarán inicialmente sus filtros actuales para no cambiar resultados silenciosamente.
- RR. HH. deberá crear y aprobar una nueva versión para convertir un filtro existente en ponderado.
- Las evaluaciones históricas permanecerán inmutables y mostrarán la política vigente al momento del cálculo.
- La reversión consistirá en volver a la versión anterior aprobada para evaluaciones futuras, sin borrar versiones ni resultados.

## Riesgos

- Configurar una penalización excesiva puede reproducir un filtro excluyente de forma encubierta; se validarán límites y se mostrará una vista previa.
- Confundir `no acreditado` con `no cumple` puede perjudicar candidatos; ambos estados tendrán etiquetas y explicaciones distintas.
- Cambiar criterios después de abrir una vacante puede alterar comparabilidad; el versionado y la reevaluación explícita preservarán trazabilidad.

## Preguntas abiertas

No quedan preguntas bloqueantes para aprobar el alcance. Los valores concretos de peso o penalización se definirán por vacante durante su configuración y no se fijan globalmente en esta spec.

## Historial

| Fecha | Decisión | Autor |
|---|---|---|
| 2026-09-11 | Se crea el borrador para evitar que un idioma no acreditado anule toda la evaluación. | Usuario / Codex |
| 2026-09-11 | Spec y plan aprobados; inicia implementación. | Responsable de producto |
| 2026-09-11 | Implementación completada; 62 pruebas focales aprobadas y suite global 286/287. | Codex |
