# SPEC-034 - Carga masiva de CV y alertas de control

- **Estado:** VERIFIED
- **Fuente:** Solicitud de RR. HH. TCS del 2026-09-14.

## Problema

RR. HH. dedica tiempo a transcribir datos que ya aparecen en los CV. Ademas, la revision separada de
las listas de excolaboradores y restricciones puede omitir alertas relevantes durante el alta.

## Usuarios y alcance

Reclutadores y administradores con acceso al cliente TCS pueden cargar entre 1 y 50 CV PDF o DOCX.
TalentIA extrae localmente los campos generales presentes, crea la ficha en la base general, conserva
el CV y muestra coincidencias con las listas TCS como alertas para revision humana.

## Requisitos

- **FR-034-001:** admitir varios CV en una misma operacion, con limite de 50 archivos.
- **FR-034-002:** extraer nombres, apellidos, documento, contacto, ubicacion, fuente, perfil,
  conocimiento tecnico, disponibilidad y expectativa salarial cuando esten explicitamente presentes.
- **FR-034-003:** crear una ficha general por identidad nueva y adjuntar su CV; una identidad exacta se
  reutiliza sin sobrescribir campos existentes y una probable queda en revision.
- **FR-034-004:** comprobar cada identidad contra ex-TCS y vetados TCS por documento exacto o, si no
  existe documento, por nombre completo exacto.
- **FR-034-005:** mostrar la alerta al terminar la carga y conservarla en la trazabilidad del candidato.
- **FR-034-006:** generar al terminar cada lote un reporte consolidado que diferencie candidatos nuevos,
  identidades ya procesadas, CV identicos, coincidencias ex-TCS, restricciones y revisiones manuales.
- **FR-034-007:** mostrar el porcentaje del lote ya procesado para que RR. HH. pueda validar el servicio
  recibido de Adecco antes de aprobarlo.
- **NFR-034-001:** extraccion y cruce locales, deterministas y sin llamadas de red.
- **SEC-034-001:** contenido con instrucciones incrustadas se bloquea antes del alta.
- **SEC-034-002:** las alertas no exponen causas sensibles ni producen rechazo automatico.
- **SEC-034-003:** solo usuarios con permisos de escritura de candidatos y documentos pueden usar el
  flujo, con aislamiento por cliente y proteccion CSRF.
- **SEC-034-004:** el reporte es informativo: no rechaza postulantes ni expone motivos sensibles de las
  listas de control.

## Fuera de alcance

OCR para imagenes sin texto, decisiones automaticas de seleccion, sobrescritura automatica de fichas,
notificaciones por correo o mensajeria y edicion de las listas de control desde esta pantalla.

## Rollback

Retirar las rutas y plantilla de carga masiva, el boton de acceso, el extractor de precarga y el
verificador inyectado. Las fichas ya confirmadas y sus eventos permanecen como registros auditables.
