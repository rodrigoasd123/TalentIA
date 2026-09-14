# Recorrido de demostracion de TalentIA

Duracion objetivo: 10 a 15 minutos.

## Preparacion

1. Instalar los extras `graph` y `benchmark`.
2. Configurar las variables de entorno sin guardar secretos en Git.
3. Ejecutar migraciones y `scripts/seed_greenfield.py`.
4. Iniciar API, worker y MLflow con la misma base y variables.
5. Crear y publicar el perfil `DEV-BACKEND-PY-DEMO` con `perfiles_demo.json`.
6. Registrar `flujo_apto` de `candidatos_demo.json` y crear su postulacion.
7. Tener una evaluacion local completada como contingencia.

## Paso 1 Inicio de sesion

- Rol practico: administrador.
- Pantalla: `/login`.
- Mostrar: sesion firmada, rol y cliente asignado.
- Resultado esperado: acceso al inicio sin exponer credenciales.

## Paso 2 Perfil y requisitos

- Pantalla: `/modulo/perfiles` y `/perfiles/nuevo`.
- Crear `Desarrollador Backend Python Demo`.
- Copiar `requisitos_texto` desde `perfiles_demo.json` y publicar la version.
- Resultado esperado: requisitos versionados con obligatoriedad, peso y CTC.

## Paso 3 AG-01 y AG-04

- Pantalla: `/candidatos/nuevo`.
- Intentar registrar el documento `45871234` despues de ejecutar el seed.
- Resultado esperado: coincidencia exacta y alta bloqueada.
- Registrar luego `flujo_apto`, cuyo documento y correo son unicos.
- Resultado esperado: nueva identidad y evento de comprobacion.
- Aclaracion: la deteccion ocurre en el formulario, antes de cargar un CV.

## Paso 4 Postulacion

- Pantalla: `/postulaciones/nueva`.
- Relacionar `flujo_apto`, la version publicada y la fuente `Adecco Demo`.
- Resultado esperado: postulacion nueva vinculada al perfil exacto.

## Paso 5 Configuracion IA

- Pantalla: `/admin/configuracion-ia`.
- Mostrar primero `local` y `deterministico-local`.
- Para proveedor externo, elegir OpenAI o Gemini, ingresar una clave fuera de camara y probarla.
- Usar temperatura `0` para una demostracion repetible.
- Resultado esperado: diagnostico seguro sin mostrar la clave ni la respuesta completa.

## Paso 6 AG-02 y AG-03

- Pantalla: `/evaluaciones/nueva`.
- Seleccionar la postulacion y cargar `CV_APTO_DEMO.docx`.
- Resultado esperado: trabajo pendiente, procesamiento del worker y evaluacion con evidencia.
- AG-02 extrae las cuatro etiquetas y retira correo, telefono y documento antes de un proveedor.
- AG-03 relaciona evidencia con los cinco requisitos. Solo AG-03 puede usar OpenAI o Gemini.

## Paso 7 Escenarios alternativos

- `CV_PARCIAL_DEMO.docx`: evidencia para Python y SQL, faltantes en otros requisitos.
- `CV_SIN_EVIDENCIA_DEMO.docx`: estructura valida, pero sin terminos del perfil.
- `CV_PROMPT_INJECTION_DEMO.docx`: sanitizacion bloquea la instruccion maliciosa.
- `CV_DUPLICADO_DEMO.docx`: acompana el caso de identidad existente; el duplicado se demuestra
  registrando el documento `45871234`, no mediante la carga del CV.

## Paso 8 Revision humana

- Pantalla: `/evaluaciones/{id}`.
- Mostrar fragmentos y posiciones de evidencia.
- Registrar una correccion con campo, valor anterior, valor verificado y justificacion.
- Resultado esperado: revision auditada. No equivale a contratar o descartar.

## Paso 9 Lotes

- Pantalla: `/lotes/nuevo`.
- Cargar `candidatos_validos.csv` para mostrar un lote directo.
- Cargar `candidatos_con_errores.csv` para mapear encabezados y corregir filas.
- Cargar `candidatos_demo.xlsx` para demostrar XLSX.
- Cargar `excolaboradores_demo.csv` con tipo excolaboradores.
- Resultado esperado: staging, clasificacion, correccion y confirmacion explicita.

## Paso 10 AG-05

- Pantalla: `/exclusiones/nueva`.
- Generar el reporte para TCS.
- Resultado esperado actual: cero exclusiones.
- Explicacion: el repositorio entrega `vigente=False` de forma conservadora hasta aprobar BIZ-001.

## Paso 11 MLflow

- Abrir `http://127.0.0.1:5000`.
- Experimento operativo: `talentia-workflows`.
- Mostrar la corrida padre `workflow-<id>` y corridas hijas por nodo.
- Revisar proveedor, modelo, estado, latencia y tokens.
- Ejecutar el benchmark y abrir el experimento `talentia-greenfield`.
- Aclarar que son corridas padre/hijo, no spans de MLflow Tracing.

## Contingencias

| Falla | Respuesta segura |
|---|---|
| El trabajo no avanza | Revisar el worker y usar la evaluacion local preparada. |
| El proveedor falla | Volver a modo local y explicar el fallback. |
| El CV pasa a revision | Mostrar el control fail-closed y usar `CV_APTO_DEMO.docx`. |
| MLflow no abre | Revisar URI en el worker y mostrar metricas operativas. |
| AG-05 no devuelve filas | Es el resultado esperado mientras BIZ-001 siga pendiente. |

## Cierre

Repetir tres ideas: los requisitos son explicitos y versionados, toda evidencia es verificable y
la decision final siempre es humana.
