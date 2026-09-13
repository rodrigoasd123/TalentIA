# Diccionario de datos greenfield

Las tablas y relaciones normativas estan declaradas en
`src/talentia/shared/infrastructure/modelos_orm.py`. Los importes usan `Numeric`, las fechas
son UTC, todas las entidades editables tienen `version` y las FK son explicitas.

Edad y variacion CTC se calculan en el dominio y no se almacenan. Documento, correo y telefono
son identificadores. BGC y Equifax tienen columnas cifradas reservadas, pero su escritura esta
bloqueada hasta resolver `BIZ-010`. Los documentos se guardan fuera de archivos estaticos.

