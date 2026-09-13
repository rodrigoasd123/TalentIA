# AG-03 — Agente evaluador

## Propósito

Comparar el CV contra el perfil solicitado y emitir un veredicto explicable antes de que el
candidato consuma tiempo de coordinación.

## Entrada

- Texto del CV o campos extraídos por AG-02.
- Perfil del puesto.
- Requisitos obligatorios y deseables.
- Versión aprobada de los criterios de evaluación.

## Proceso

Evalúa cada requisito de forma individual. Para cada uno determina si:

- se cumple;
- no se cumple; o
- no existe información suficiente.

Cada resultado debe indicar de qué parte del documento proviene la evidencia. El modelo propone
la evaluación estructurada; las reglas aprobadas del backend calculan el puntaje, aplican filtros
y determinan el estado operativo.

## Salida

- Veredicto global.
- Detalle por requisito.
- Estado de cada requisito.
- Evidencia textual y fuente.
- Sustento legible para revisión humana.
- Puntaje calculado por el backend.

## Valores de veredicto

| Veredicto | Condición |
|---|---|
| **CUMPLE** | Todos los requisitos obligatorios se verifican con evidencia. |
| **CUMPLE PARCIALMENTE** | Se verifican los obligatorios pero faltan deseables, o un obligatorio se cumple de forma parcial. |
| **NO CUMPLE** | Al menos un requisito obligatorio no se verifica. |
| **REQUIERE REVISIÓN** | El documento no contiene información suficiente para decidir. |

## Restricciones

- No utiliza edad, género, origen, estado civil ni características protegidas.
- Estos campos se eliminan antes de enviar contexto al modelo.
- No decide contratación, rechazo ni avance de etapa.
- No puede modificar la postulación por sí mismo.
- Un requisito sin evidencia no debe presentarse como cumplido.
- Los criterios excluyentes, pesos y penalizaciones provienen únicamente de la política aprobada.
- Toda evaluación debe quedar versionada y auditada.

## API conceptual

```http
POST /api/agentes/evaluacion
```

Solicitud:

```json
{
  "candidato_id": "...",
  "perfil_id": "...",
  "cv_texto": "..."
}
```

Respuesta:

```json
{
  "veredicto": "CUMPLE_PARCIALMENTE",
  "perfil_version": 3,
  "requisitos": [
    {
      "nombre": "Java",
      "estado": "CUMPLE",
      "anios_detectados": 6,
      "evidencia": "Desarrollador Java Senior, 2019-2025"
    },
    {
      "nombre": "Quarkus",
      "estado": "SIN_EVIDENCIA",
      "evidencia": null
    }
  ],
  "sustento": "Cumple los dos requisitos obligatorios. No se encontró evidencia de Quarkus."
}
```

## Criterio de aceptación

Cada requisito evaluado debe incluir evidencia textual o declarar explícitamente que no hay
evidencia suficiente. Un veredicto sin sustento se considera un defecto bloqueante.
