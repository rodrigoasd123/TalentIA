# Manual de usuario — TalentIA

## 1. Propósito

TalentIA es un ATS que apoya a Recursos Humanos de TCS en el registro de candidatos, perfiles,
postulaciones, CV, evaluaciones documentales, revisión humana, importaciones y trazabilidad.

TalentIA **no contrata, aprueba ni rechaza automáticamente**. Los resultados son evidencia de
apoyo; la decisión final siempre corresponde a una persona autorizada.

## 2. Acceso

1. Confirme con el operador que la API y el worker estén activos.
2. Abra http://127.0.0.1:8000/login.
3. Ingrese el correo y la contraseña entregados por el administrador.
4. Para salir, use **Cerrar sesión** en la parte inferior del menú.

La sesión expira por inactividad. Cinco intentos fallidos consecutivos bloquean temporalmente la
cuenta con la configuración predeterminada.

La prueba local por HTTP se ejecuta en modo de desarrollo. El ambiente piloto requiere HTTPS para
proteger la cookie de sesión.

## 3. Roles

| Rol | Uso principal |
|---|---|
| Administrador | Acceso completo y administración de usuarios |
| Reclutador | Candidatos, postulaciones, CV y solicitud de evaluaciones |
| Gestor de contratación | Perfiles, revisión humana y reportes |
| Entrevistador | Consulta de candidatos y resolución de revisiones |
| Auditor | Auditoría y reportes |
| Importador | Lotes y comprobación de excolaboradores |

No ver una acción normalmente significa que la cuenta no tiene el permiso o cliente requerido.

## 4. Navegación

- **Inicio:** actividad reciente y estado del proveedor de IA.
- **Base general:** búsqueda, creación, edición y trazabilidad de candidatos.
- **Perfiles:** perfiles de puesto y versiones de requisitos.
- **Postulaciones:** relación entre candidato, perfil y fuente.
- **CV y precarga:** carga de PDF/DOCX e inicio de evaluación.
- **Evaluaciones:** resultados documentales y acceso al detalle.
- **Revisión humana:** casos pendientes de decisión o corrección.
- **Trabajos:** progreso y errores de las evaluaciones.
- **Lotes:** importación gobernada de CSV/XLSX.
- **Ex-TCS:** importación y comprobación de excolaboradores.
- **Exclusiones:** reportes para revisión de proveedor.
- **Métricas:** indicadores operativos.
- **Usuarios:** roles y clientes; disponible para administradores.

## 5. Flujo recomendado

### 5.1 Registrar o localizar un candidato

1. Entre a **Base general**.
2. Busque primero por nombre, correo o documento.
3. Si no existe, seleccione **Nuevo candidato**.
4. Complete cliente, nombres y apellidos. Documento, correo, teléfono, fuente, reclutador,
   disponibilidad y datos salariales mejoran la trazabilidad.
5. Seleccione **Registrar candidato**.

TalentIA muestra posibles coincidencias antes de crear la identidad. Revise el criterio, estado,
fecha y reclutador. Confirme una identidad separada únicamente si verificó que son personas
distintas. El sistema nunca fusiona candidatos automáticamente.

### 5.2 Editar un candidato

1. Abra el candidato desde la tabla.
2. Seleccione **Editar candidato**.
3. Modifique los datos y pulse **Guardar cambios**.

Cada cambio incrementa la versión y genera trazabilidad. Si otra persona cambió el registro al
mismo tiempo, recargue la ficha y aplique el cambio sobre la versión más reciente.

### 5.3 Crear un perfil

1. Entre a **Perfiles** y pulse **Crear perfil**.
2. Seleccione cliente e ingrese código y título.
3. Pulse **Crear y agregar versión**.
4. Registre un requisito por línea con este formato:

       CODIGO | descripción | obligatorio/opcional | peso

   Ejemplo:

       PY | Experiencia con Python | obligatorio | 1

5. Ingrese el CTC cuando corresponda.
6. Marque **Publicar versión para postulaciones** y guarde.

Crear una nueva versión preserva los requisitos históricos de evaluaciones anteriores.

### 5.4 Crear una postulación

1. Entre a **Postulaciones** y pulse **Crear postulación**.
2. Seleccione cliente, candidato y versión publicada del perfil.
3. Registre la fuente real, por ejemplo Adecco, LinkedIn, Referido o Directa.
4. Pulse **Crear postulación**.

### 5.5 Cargar un CV y evaluar

1. Entre a **CV y precarga** y pulse **Cargar CV y evaluar**.
2. Seleccione la postulación.
3. Adjunte un PDF o DOCX. El límite predeterminado es 10 MB.
4. Pulse **Cargar e iniciar evaluación**.
5. Revise el trabajo hasta que termine o requiera atención.

El CV se almacena en un área privada. El worker debe estar activo para procesar la cola.

### 5.6 Interpretar la evaluación

El detalle muestra candidato, perfil, documento, puntaje documental, motor, versión, explicación y
evidencia por requisito. Cada evidencia incluye página, posiciones y fragmento.

**Sin evidencia suficiente no significa incumplimiento.** Significa que el dato debe validarse
mediante revisión humana, entrevista, prueba técnica u otra fuente autorizada.

### 5.7 Registrar una decisión humana

1. Revise los requisitos y la evidencia.
2. Elija **Aceptar sugerencia**, **Corregir evaluación** o **Rechazar sugerencia**.
3. Escriba una justificación.
4. Para una corrección, indique campo, valor anterior y valor verificado.
5. Pulse **Guardar decisión auditada**.

Aceptar o rechazar se refiere a la sugerencia documental, no a contratar o descartar
automáticamente a la persona.

## 6. Importaciones y excolaboradores

### Importar candidatos

1. Entre a **Lotes** y pulse **Importar archivo**.
2. Seleccione cliente, tipo Candidatos y un CSV/XLSX.
3. Revise la vista previa.
4. Mapee columnas y corrija filas observadas.
5. Confirme solo cuando la vista previa sea correcta.

Los registros no se incorporan definitivamente mientras el lote permanezca en staging. También
puede cancelarlo.

### Comprobar ex-TCS

Desde la pantalla de importación puede cargar un lote de excolaboradores o consultar un documento
individual. Una coincidencia se deriva a revisión humana y no produce exclusión automática.

## 7. Exclusiones, métricas y usuarios

- En **Exclusiones**, genere el reporte, seleccione cliente y revise el resultado antes de
  compartirlo o descargarlo.
- En **Métricas**, consulte los indicadores del alcance autorizado.
- En **Usuarios**, el administrador asigna o retira roles y clientes. Debe aplicar mínimo
  privilegio y nunca compartir cuentas.

## 8. Modo manual y problemas frecuentes

Si aparece **Modo manual**, no hay un proveedor LLM activo. El expediente, las reglas
determinísticas y la revisión humana siguen funcionando.

| Situación | Acción |
|---|---|
| No puede iniciar sesión | Verifique credenciales o espere el desbloqueo |
| El trabajo no avanza | Confirme que el worker esté activo |
| CV ilegible | Registre la observación y use revisión manual |
| Falta evidencia | No asuma incumplimiento; solicite validación humana |
| Posible duplicado | Revise coincidencias antes de crear otra identidad |
| Archivo rechazado | Use PDF/DOCX válido y compruebe el tamaño |
| Acceso denegado | Solicite el rol y cliente estrictamente necesarios |
| Cambio concurrente | Recargue y vuelva a editar la última versión |

## 9. Privacidad y uso responsable

- Trate los CV y datos personales como información confidencial.
- No utilice CV reales en una demostración sin autorización.
- No copie API keys, contraseñas o secretos en formularios o capturas.
- No use atributos protegidos para puntuar o descartar candidatos.
- Verifique la evidencia y documente siempre la decisión humana.
- Cierre la sesión al terminar.

## 10. Recorrido rápido para una demostración

1. Inicie sesión.
2. Revise los datos ficticios en **Base general**.
3. Registre un candidato con correo y documento únicos.
4. Cree una postulación con un perfil publicado.
5. Cargue un CV ficticio desde **CV y precarga**.
6. Observe el trabajo y abra la evaluación.
7. Revise evidencia y registre una decisión humana justificada.
8. Muestre la trazabilidad y las métricas.

## 11. Ayuda técnica

Consulte [Instalación en Windows](docs/INSTALACION_GREENFIELD_WINDOWS.md) y el
[runbook del piloto](docs/pilot_runbook.md).
