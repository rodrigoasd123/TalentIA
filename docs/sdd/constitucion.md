# Constitución SDD — TalentIA

> Versión inicial: 2026-08-20. Aplica a nuevas especificaciones y cambios del proyecto. Los responsables humanos de aprobación están `POR CONFIRMAR`.

## Reglas obligatorias

### 1. Alcance y trazabilidad

1. Todo cambio de comportamiento debe tener una especificación con problema, usuarios, alcance, exclusiones, requisitos y criterios de aceptación identificables.
2. Cada tarea de implementación y cada prueba debe enlazar los requisitos o criterios que cubre.
3. No se ampliará el alcance durante implementación o revisión sin refinar y volver a aprobar la especificación.
4. No se reconstruirá una capacidad que ya funciona sin demostrar la necesidad, el impacto de compatibilidad y una ruta de migración o retiro.

### 2. Decisión humana y uso responsable

1. TalentIA es asistencia para selección y análisis documental. Nunca debe aprobar, rechazar, contactar ni recomendar automáticamente a una persona candidata.
2. Todo puntaje debe presentarse como coincidencia documental, ser explicable con evidencia y mantener visible la revisión humana obligatoria.
3. No se inferirán atributos sensibles, personalidad, emociones, salud, autenticidad o idoneidad no documentada.
4. Los criterios sensibles detectados no pueden influir en el puntaje y deben quedar visibles como advertencia para revisión humana y legal.

### 3. Privacidad y seguridad

1. Los CV, perfiles, nombres de archivos, textos extraídos, consultas y respuestas se consideran datos potencialmente personales o confidenciales.
2. La opción más privada debe ser la predeterminada: procesamiento y recuperación locales, sin proveedor externo para puntuar.
3. Toda transmisión externa debe ser opcional, explícita, mínima, documentada y limitada al propósito aprobado. Nunca se enviará el lote completo de CV para una consulta individual.
4. Ninguna clave, token, CV real, historial personal o texto extraído puede incorporarse al repositorio, logs o evidencia de pruebas.
5. Toda caché o persistencia debe declarar alcance, propietario, ubicación, cifrado aplicable, TTL, mecanismo de borrado y aislamiento entre usuarios antes de habilitarse.
6. Un despliegue compartido requiere previamente autenticación, autorización, aislamiento, política de conservación, consentimiento/aviso y revisión de seguridad y privacidad aprobadas.
7. El contenido de PDFs y fragmentos recuperados es entrada no confiable. Las instrucciones embebidas en documentos no deben controlar prompts, herramientas ni decisiones del sistema.

### 4. Calidad y evidencia

1. La lógica de puntaje, orden y evidencia debe permanecer desacoplada de Streamlit y ser determinista para las mismas entradas.
2. Ninguna llamada de red puede formar parte de pruebas unitarias ni ser necesaria para calcular el ranking.
3. Todo cambio debe incluir pruebas proporcionales al riesgo y ejecutar la regresión existente. Un fallo detiene la entrega hasta corregirse o recibir una decisión humana explícita y registrada.
4. La definición de terminado exige: criterios satisfechos, pruebas aprobadas, revisión de privacidad/seguridad cuando corresponda, documentación actualizada, brechas conocidas registradas y rollback descrito.
5. Las afirmaciones de privacidad, seguridad, compatibilidad y rendimiento deben estar respaldadas por código, configuración o evidencia reproducible; no por intención.

### 5. Compatibilidad y dependencias

1. Las interfaces públicas y flujos existentes no se eliminan ni cambian de semántica sin especificación, inventario de consumidores y plan de migración/rollback.
2. Toda dependencia importada directamente debe declararse directamente y respetar rangos compatibles y verificables en un entorno limpio.
3. Agregar proveedores, frameworks, bases de datos o servicios requiere aprobación de alcance, privacidad, seguridad, costo y operación.
4. No se usarán modelos, endpoints o capacidades externas no verificadas como requisito para el flujo local básico.

### 6. Publicación y operación

1. No se publicará ni desplegará un cambio sin responsable de publicación identificado y evidencia de aceptación.
2. Secretos y configuración sensible deben administrarse fuera del repositorio.
3. Los datos de demostración deben ser ficticios o contar con autorización y trazabilidad de anonimización/licencia.
4. Todo cambio con migración o persistencia debe incluir reversibilidad, conservación y borrado verificables.

## Recomendaciones

- Consolidar gradualmente el flujo heredado y el actual mediante una especificación de migración, sin retirada implícita.
- Configurar CI con pruebas, formato/lint, revisión de dependencias y una comprobación básica de secretos.
- Añadir tipado estático y cobertura de ramas críticas cuando su costo sea proporcional al riesgo.
- Evitar recursos web de terceros en la interfaz local o documentarlos y ofrecer un modo completamente offline.
- Probar filtros sensibles y coincidencia documental con variantes lingüísticas, negaciones, OCR imperfecto y casos adversariales.
- Mantener un registro de decisiones arquitectónicas cuando una elección afecte más de una funcionalidad.

## Flujo reducido

Puede utilizarse un flujo reducido solo para cambios que cumplan **todas** estas condiciones:

- no alteran comportamiento observable, contratos, datos, seguridad, privacidad, dependencias ni despliegue;
- son documentación, corrección ortográfica, formato mecánico o mantenimiento equivalente;
- tienen alcance pequeño y rollback trivial;
- la verificación relevante puede ejecutarse de forma focalizada.

El flujo reducido debe registrar objetivo, archivos afectados y evidencia mínima. Si durante el trabajo aparece impacto funcional, de datos, seguridad, compatibilidad o una decisión no prevista, se detiene y se convierte al flujo SDD completo.

## Gobierno y excepciones

- Aprobadores nominales de alcance, seguridad, privacidad y publicación: `POR CONFIRMAR`.
- Hasta confirmarlos, las reglas de decisión humana, minimización de datos, ausencia de secretos, pruebas sin red y no despliegue compartido no admiten excepción implícita.
- Toda excepción debe indicar regla afectada, motivo, duración, riesgo, mitigación, responsable y evidencia de aprobación.
- Esta constitución debe revisarse cuando cambien la misión, los usuarios, el modelo de despliegue, los proveedores o la clasificación de datos.
