# Base de Datos Simulada de Excolaboradores - TCS Perú

Este conjunto de datos simula el historial de desvinculaciones y registros de excolaboradores de **Tata Consultancy Services (TCS Perú)**. Está diseñado para alimentar las validaciones automáticas y la comprobación de reingreso en **TalentIA**.

## Archivos Incluidos:
1. `excolaboradores_tcs_simulados.csv`: Base de datos completa con historial contractual, cargos, proyectos, fechas de entrada/salida y evaluación de RRHH.
2. `lote_importacion_excolaboradores_tcs.csv`: Archivo preparado con el formato exacto requerido por TalentIA para carga masiva en el módulo `/lotes/nuevo`.

## Estructura de Campos (`excolaboradores_tcs_simulados.csv`):
- `documento`: DNI del excolaborador (8 dígitos).
- `nombres` y `apellidos`: Identidad del profesional.
- `cargo_desempenado`: Último puesto ocupado en TCS (ej. Desarrollador Backend, Tech Lead, DevOps).
- `area_o_proyecto`: Cuenta o cliente asignado (ej. BCP, BBVA, Interbank, Rimac Seguros).
- `fecha_ingreso`: Fecha formal de contratación (YYYY-MM-DD).
- `fecha_salida`: Fecha formal de cese o desvinculación (YYYY-MM-DD).
- `tiempo_permanencia_meses`: Antigüedad total en meses en la compañía.
- `motivo_salida`: Justificación de la salida (Renuncia voluntaria, fin de proyecto, despido disciplinario, bajo rendimiento).
- `calificacion_desempeno`: Evaluación técnica y conductual registrada al cese (Sobresaliente A+, Excelente A, Bueno B, Regular C, Deficiente D).
- `elegible_reingreso`: `SI` (recontratable sin objeción) o `NO` (bloqueo / observación de RRHH).
- `observaciones_rrhh`: Dictamen cualitativo y recomendaciones de RRHH.

## Casos de Prueba Clave en TalentIA:
- **DNI 45871234 (Carlos Alberto Mendoza Ramos)**: Ex-TCS Senior Python. Salida voluntaria por mejor oferta. **Elegible: SI**.
- **DNI 49345678 (Martín Gonzalo Rojas Paredes)**: Ex-TCS Java. Despido justificado por falta grave (abandono). **Elegible: NO** (Activa alerta de revisión humana).
- **DNI 51567890 (Jorge Luis Navarro Salgado)**: Ex-TCS DevOps. Período de prueba no superado. **Elegible: NO**.
