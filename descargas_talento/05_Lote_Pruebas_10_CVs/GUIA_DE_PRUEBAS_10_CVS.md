# Guía de Casos de Prueba - Lote de 10 CVs para TalentIA

Este lote ha sido diseñado específicamente para validar de forma exhaustiva los motores de extracción automática y alertas de control de TalentIA.

| N° | Archivo | Candidato | DNI | Caso de Uso | Comportamiento / Alerta Esperada |
|---|---|---|---|---|---|
| 1 | `01_CV_Gonzalo_Benavides_Apto_Limpio.docx` | Gonzalo Javier Benavides Rivas | `72109845` | Candidato 100% Apto / Limpio (Sin antecedentes en bases TCS) | **Sin alertas (Apto / Registrado)** |
| 2 | `02_CV_Mariana_Quiroz_Apto_Limpia.docx` | Mariana Alejandra Quiroz Tello | `73450912` | Candidata 100% Apta / Limpia para QA Automation | **Sin alertas (Apto / Registrado)** |
| 3 | `03_CV_Carlos_Mendoza_ExTCS_Elegible.docx` | Carlos Alberto Mendoza Ramos | `45871234` | Excolaborador TCS con salida voluntaria y calificación sobresaliente (Elegible para Reingreso) | **Alerta Informativa: Coincidencia con excolaborador TCS elegible para reingreso** |
| 4 | `04_CV_Lucia_Vargas_ExTCS_Elegible.docx` | Lucia Mariana Vargas Silva | `46982345` | Excolaboradora TCS con salida por cierre de proyecto (Calificación A - Excelente) | **Alerta Informativa: Coincidencia con excolaborador TCS elegible para reingreso** |
| 5 | `05_CV_Martin_Rojas_ExTCS_NoElegible_y_Vetado.docx` | Martin Gonzalo Rojas Paredes | `49345678` | Excolaborador TCS NO Elegible (Falta grave por abandono de puesto) y Vetado Permanente | **Doble Alerta Alta: Excolaborador TCS no elegible + Restricción de veto vigente** |
| 6 | `06_CV_Jorge_Navarro_ExTCS_NoElegible_Carencia.docx` | Jorge Luis Navarro Salgado | `51567890` | Excolaborador TCS No Elegible (No superó período de prueba técnico) con período de enfriamiento | **Alerta Alta: Excolaborador TCS no elegible (Revisión obligatoria)** |
| 7 | `07_CV_Camila_Caceres_Vetada_Confidencialidad.docx` | Camila Andrea Caceres Torres | `54890123` | Postulante Vetada de TCS (Veto Permanente por violación grave de confidencialidad bancaria) | **Alerta Crítica / Alta: Coincidencia con una restricción vigente (Veto Permanente)** |
| 8 | `08_CV_Braulio_Paredes_Vetado_TituloAdulterado.docx` | Braulio Marcelo Paredes Quispe | `71829304` | Postulante Vetado Permanente (Título y certificados adulterados detectados en verificación BGC) | **Alerta Crítica / Alta: Coincidencia con una restricción vigente (Veto Permanente)** |
| 9 | `09_CV_Javier_Villalobos_Vetado_ConflictoInteres.docx` | Javier Eduardo Villalobos Ruiz | `34125678` | Postulante con Inhabilitación Ético-Legal Activa (Conflicto de interés y competencia desleal comprobada) | **Alerta Alta: Coincidencia con restricción activa de cumplimiento** |
| 10 | `10_CV_Duplicado_Gonzalo_Benavides.docx` | Gonzalo Javier Benavides Rivas | `72109845` | Candidato Duplicado (Mismo DNI que el CV 01) para validar que no cree duplicados en BD | **Estado: REUTILIZADO (No crea doble ficha, conserva histórico y agrega documento)** |


### Instrucciones para probar en la Web:
1. Ingresa a `http://127.0.0.1:8000/candidatos/importar-cvs`
2. Selecciona varios o todos los archivos de este directorio.
3. Presiona **Importar currículums**.
4. Observa cómo el sistema autocompleta la base general y levanta las alertas amarillas y rojas con los antecedentes.
5. Sube el archivo `10_CV_Duplicado_Gonzalo_Benavides.docx` para comprobar que el sistema detecta la identidad exacta y lo marca como **reutilizado** sin crear duplicados.
