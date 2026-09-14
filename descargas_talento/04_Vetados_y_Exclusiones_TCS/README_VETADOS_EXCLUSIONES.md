# Base de Datos Simulada de Vetados y Exclusiones - TCS Perú (AG-05)

Este conjunto de datos simula el registro centralizado de **vetos, inhabilitaciones y períodos de carencia (cooling-off)** para candidatos y expostulantes en **TCS**. Representa la fuente de verdad consumida por el componente **AG-05 (Exclusiones y Cumplimiento)** de TalentIA.

## Archivos Incluidos:
1. `vetados_excluidos_tcs_simulados.csv`: Registro exhaustivo con motivos específicos de exclusión, tipo de restricción, vigencias y sustentación legal/ética.
2. `reporte_exclusiones_oficial_tcs.csv`: Reporte oficial exportable para agencias proveedoras de personal, donde se enmascaran las causas sensibles en un motivo genérico por cumplimiento normativo.

## Estructura de Campos (`vetados_excluidos_tcs_simulados.csv`):
- `documento`: DNI de la persona excluida.
- `nombres` y `apellidos`: Datos de identidad.
- `fecha_evento`: Fecha en que se materializó la causal de descarte o sanción.
- `tipo_restriccion`:
  - `Veto Permanente`: Sanciones irreversibles (fraude documental, suplantación, violación de código de ética).
  - `Período de Carencia (Cooling-off)`: Bloqueo temporal reglamentario (ej. 6 meses por descarte técnico, 12 meses por PIP).
  - `Inhabilitación Ético-Legal`: Faltas con repercusión jurídica (conflicto de interés, acoso, competencia desleal).
  - `Descarte por Integridad / BGC`: Observaciones negativas en Background Check o Veripol.
- `motivo_descarte`: Causa detallada y específica del veto o exclusión.
- `vigencia_meses`: Duración del bloqueo en meses (999 representa permanente).
- `fecha_fin_veto`: Fecha exacta en que expira la restricción o "Indefinida".
- `estado_restriccion`: `Permanente`, `Activa` o `Vencida`.
- `responsable_registro`: Órgano emisor (Comité de Ética, BGC Unit, Asesoría Legal, Talent Acquisition).
- `observaciones_legales`: Respaldo normativo y expediente asociado.

## Casos de Prueba Clave en AG-05:
- **DNI 54890123 (Camila Cáceres)**: Filtración de logs bancarios confidenciales. Veto Permanente.
- **DNI 71829304 (Braulio Paredes)**: Presentó título universitario adulterado. Veto Permanente.
- **DNI 74150637 (Fiorella Salas)**: Carencia de 6 meses por entrevista técnica desaprobada.
- **DNI 75261748 (Guillermo Peña)**: Suplantación de identidad en evaluación online. Veto Permanente.
