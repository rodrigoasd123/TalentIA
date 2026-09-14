# Kit de demostracion profesional de TalentIA

Este directorio contiene exclusivamente datos ficticios para demostrar la implementacion actual de
TalentIA. No contiene claves, contrasenas, bases SQLite ni datos personales reales.

## Inventario

| Archivo | Funcionalidad | Agente | Resultado esperado |
|---|---|---|---|
| `cvs/CV_APTO_DEMO.docx` | Extraccion y evaluacion completa | AG-02 y AG-03 | Cuatro campos extraidos y evidencia para los requisitos del perfil. |
| `cvs/CV_PARCIAL_DEMO.docx` | Evaluacion incompleta | AG-02 y AG-03 | Extraccion completa, coincidencias parciales y revision humana. |
| `cvs/CV_SIN_EVIDENCIA_DEMO.docx` | Ausencia de evidencia | AG-02 y AG-03 | Campos estructurados, sin evidencia suficiente del perfil. |
| `cvs/CV_DUPLICADO_DEMO.docx` | Expediente del caso duplicado | AG-01 y AG-04 | El documento `45871234` bloquea el alta antes de cargar el CV. |
| `cvs/CV_PROMPT_INJECTION_DEMO.docx` | Defensa ante instrucciones incrustadas | Guardrail previo a AG-02/AG-03 | Procesamiento bloqueado y derivado a revision segura. |
| `lotes/candidatos_validos.csv` | Importacion directa | AG-01/AG-04 en persistencia | Cinco filas nuevas listas para confirmar. |
| `lotes/candidatos_con_errores.csv` | Mapeo y correccion | Importador | Encabezados a mapear, apellido faltante, correo invalido y duplicado interno. |
| `lotes/candidatos_demo.xlsx` | Importacion XLSX | Importador | Cuatro candidatos sinteticos listos para staging. |
| `lotes/excolaboradores_demo.csv` | Lista de ex-TCS | AG-05 como insumo independiente | Cuatro referencias hash con elegibilidad si/no/desconocida. |
| `datos/perfiles_demo.json` | Perfil versionado | AG-03 | Perfil publicado con cinco requisitos ponderados. |
| `datos/candidatos_demo.json` | Altas manuales y casos | AG-01 y AG-04 | Candidato nuevo, duplicado, parcial, sin evidencia e inyeccion. |
| `datos/recorrido_demo.md` | Guion operativo | Todos | Recorrido reproducible de 10 a 15 minutos. |

## Datos que deben existir en SQLite

Antes de presentar, prepare como minimo:

1. El cliente TCS.
2. Una cuenta administradora provisionada por variables de entorno.
3. Los roles del sistema y acceso de la cuenta al cliente TCS.
4. Un perfil publicado con los requisitos de `perfiles_demo.json`.
5. El candidato `flujo_apto` de `candidatos_demo.json`.
6. Una postulacion de ese candidato al perfil publicado.
7. El candidato sembrado con documento `45871234` para demostrar coincidencia exacta.

`scripts/seed_greenfield.py` crea el cliente TCS, tres convocatorias, 25 candidatos y sus
postulaciones. No crea usuarios ni contrasenas.

## Usuarios y roles

| Cuenta sugerida | Rol | Uso en la demo |
|---|---|---|
| `admin.demo@example.test` | administrador | Recorrido completo y configuracion IA. |
| `reclutador.demo@example.test` | reclutador | Candidatos, postulaciones, CV y evaluaciones. |
| `gestor.demo@example.test` | gestor_contratacion | Perfiles, revisiones y reportes. |
| `entrevistador.demo@example.test` | entrevistador | Consulta y revision humana. |
| `auditor.demo@example.test` | auditor | Metricas y reportes. |
| `importador.demo@example.test` | importador | Lotes y excolaboradores. |

La aplicacion solo provisiona automaticamente al administrador y permite asignar roles/clientes a
usuarios existentes. No existe alta de usuarios en la interfaz. Para una demo portable, use la
cuenta administradora y explique los actores ideales. Si ya dispone de cuentas operativas, asigne
sus roles y clientes sin guardar sus contrasenas en este directorio.

## Orden de preparacion

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[graph,benchmark]"

$env:TALENTIA_ENV="desarrollo"
$env:TALENTIA_SESSION_SECRET="<secreto-de-al-menos-32-caracteres>"
$env:TALENTIA_ADMIN_EMAIL="<correo-administrador>"
$env:TALENTIA_ADMIN_PASSWORD="<contrasena-segura>"
$env:TALENTIA_MLFLOW_TRACKING_URI="sqlite:///mlflow.db"
$env:TALENTIA_MLFLOW_URL="http://127.0.0.1:5000"

.\scripts\migrate.ps1
.\.venv\Scripts\python.exe scripts\seed_greenfield.py
```

No reemplace los marcadores de secretos dentro de este README. Configure valores reales solamente
en la terminal o en el mecanismo de secretos aprobado.

## Procesos de la demo

Inicie cada comando en una terminal con el mismo entorno:

```powershell
.\scripts\start_api.ps1
```

```powershell
.\scripts\start_worker.ps1
```

```powershell
.\.venv\Scripts\mlflow.exe server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000
```

Direcciones:

- TalentIA: `http://127.0.0.1:8000/login`
- Configuracion IA: `http://127.0.0.1:8000/admin/configuracion-ia`
- MLflow: `http://127.0.0.1:5000`

## Perfil de demostracion

Use el perfil `Desarrollador Backend Python Demo`. El formulario acepta una linea por requisito:

```text
PYTHON | Experiencia con Python | obligatorio | 3
FASTAPI | Experiencia con FastAPI | obligatorio | 3
SQL | Conocimientos de SQL o PostgreSQL | obligatorio | 2
DOCKER | Experiencia con Docker | opcional | 1
INGLES | Nivel de ingles B2 | opcional | 1
```

AG-02 reconoce estas etiquetas en el CV:

```text
Habilidades:
Experiencia:
Educacion:
Empresa reciente:
```

La falta de cualquiera de los cuatro campos deriva el caso a revision. Correo, telefono y documento
se retiran antes de usar un proveedor externo.

## Lotes

El importador admite `.csv` UTF-8 y `.xlsx`, entre 1 y 5000 filas.

Para candidatos admite `nombres`, `apellidos`, `tipo_documento`, `documento`, `correo` y `telefono`.
Solo `nombres` y `apellidos` son obligatorios. Para excolaboradores admite `documento` y
`elegible_reingreso`; `documento` es obligatorio.

El flujo es carga, staging, mapeo, correccion y confirmacion. Una fila `exacta` se omite. Una fila
`invalida` o `requiere_revision` bloquea la confirmacion hasta corregirse.

## AG-05

La implementacion actual consulta candidatos para exclusiones con `vigente=False`. No se deben
fabricar datos para eludir esa regla. El resultado esperado es un CSV sin exclusiones, hasta que
BIZ-001 defina vigencias y motivos aprobados.

Estado honesto: AG-05 esta implementado parcialmente.

## Configuracion de OpenAI o Gemini

El modo local no requiere API key. Para un proveedor externo, el administrador selecciona proveedor
y modelo en `/admin/configuracion-ia`, introduce la clave fuera de camara, usa temperatura baja y
ejecuta el diagnostico. La clave se cifra en SQLite y no se muestra de nuevo.

Solo AG-03 puede consumir OpenAI o Gemini. AG-01, AG-02, AG-04 y AG-05 permanecen deterministas.
El proveedor y modelo son globales; no existe asignacion independiente por agente.

## Resultado esperado en MLflow

Con `TALENTIA_MLFLOW_TRACKING_URI` presente en el worker, el experimento `talentia-workflows`
contiene una corrida padre `workflow-<id>` y corridas hijas por nodo. Revise:

- `talentia.trabajo_id`, `talentia.correlacion_id`, proveedor, modelo y estado.
- `latencia_total_ms` y latencia por nodo.
- `prompt_tokens`, `completion_tokens` y `total_tokens`.
- `talentia.privacidad=metadata-only`.

La implementacion usa corridas padre/hijo mediante `MlflowClient`; no usa spans nativos de MLflow
Tracing. No espere contenido del CV, prompts ni respuestas en MLflow.

Para el benchmark:

```powershell
.\.venv\Scripts\python.exe scripts\ejecutar_benchmark_greenfield.py
```

El experimento `talentia-greenfield` registra el benchmark determinista AG-02/AG-03. No existe una
comparacion automatica completa de calidad o costo monetario entre varios LLM.

## Funcionalidades no demostrables como completas

- Creacion de usuarios desde la aplicacion.
- Asignacion de un modelo distinto por agente.
- Costo monetario por modelo.
- Spans nativos de MLflow Tracing.
- OCR conectado para PDF escaneado.
- Exclusiones reales mientras BIZ-001 permanezca pendiente.
- Benchmark automatico completo de calidad entre varios proveedores.
- Una pantalla autonoma de auditoria para el rol auditor.

## Riesgos y contingencias

| Riesgo | Contingencia |
|---|---|
| LangGraph o MLflow no instalado | Instalar `.[graph,benchmark]` antes de la demo. |
| Worker detenido | Iniciarlo y conservar una evaluacion completada como respaldo. |
| API key o modelo no disponible | Volver a `local` y continuar con el motor determinista. |
| CV sin las cuatro etiquetas | Usar `CV_APTO_DEMO.docx`. |
| Prompt injection | Mostrar el bloqueo seguro; no intentar omitirlo. |
| MLflow sin corridas | Confirmar la URI en el entorno del worker. |
| Reporte AG-05 vacio | Explicar BIZ-001; es el comportamiento esperado. |

## Checklist final

- [ ] API activa en `127.0.0.1:8000`.
- [ ] Worker activo con la misma base SQLite.
- [ ] MLflow activo en `127.0.0.1:5000`.
- [ ] Administrador puede iniciar sesion.
- [ ] Datos sinteticos sembrados.
- [ ] Perfil de demo publicado.
- [ ] Candidato y postulacion preparados.
- [ ] `CV_APTO_DEMO.docx` validado.
- [ ] Configuracion IA en local o diagnostico externo exitoso.
- [ ] Evaluacion local de contingencia completada.
- [ ] Corrida padre e hijas visibles en MLflow.
- [ ] Lotes revisados antes de confirmar.
- [ ] Ninguna pantalla muestra claves ni datos reales.
- [ ] Se explica que la decision final es humana.
- [ ] No se promete costo, tracing nativo, OCR ni comparacion multi-LLM completa.

El guion detallado esta en `datos/recorrido_demo.md`.
