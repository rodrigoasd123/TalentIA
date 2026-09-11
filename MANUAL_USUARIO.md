# Manual de usuario — TalentIA

## 1. Qué hace la aplicación

TalentIA administra el proceso de selección e integra la comparación de CV en PDF con los requisitos explícitos de un perfil de puesto. Presenta un orden de revisión, un puntaje documental y la evidencia encontrada en cada CV. La decisión de continuar o no con un candidato pertenece siempre al equipo de Recursos Humanos.

La aplicación no verifica la autenticidad del CV, no evalúa personalidad y no debe usarse como mecanismo automático de contratación o descarte.

## 2. Requisitos

- Windows 10 u 11.
- Python 3.10 o superior.
- Un PDF con el perfil del puesto.
- Entre uno y veinte CV en PDF.
- Internet solo para instalar dependencias y, opcionalmente, usar Gemini.

## 3. Instalación

Extrae el ZIP del repositorio. No ejecutes el proyecto dentro del ZIP. Abre PowerShell en la carpeta y ejecuta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activación:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 4. Ejecutar

```powershell
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
python -m streamlit run ats_frontend/streamlit_app.py
```

Abre `http://localhost:8501`. Mantén la terminal abierta y usa `Ctrl+C` para detener el programa.

## 5. Revisar un lote de CV

1. Elige el método de lectura:
   - **Normal:** PDF digital con texto seleccionable.
   - **OCR:** PDF escaneado o compuesto por imágenes. Es local y puede tardar más.
2. Carga el **perfil del puesto o convocatoria**.
3. Carga uno o varios **CV de postulantes**.
4. Espera a que aparezca el mensaje de procesamiento exitoso.
5. Abre **Ranking orientativo** para priorizar la lectura.
6. En **Detalle por CV**, selecciona un archivo y revisa:
   - texto exacto del requisito;
   - página del perfil;
   - porcentaje de cobertura;
   - términos encontrados;
   - página y fragmento del CV.
7. Usa **Fuentes** para comprobar el texto extraído completo.

Los estados significan:

- **Coincidencia alta:** al menos 75 % de los términos del requisito aparecen en el CV.
- **Coincidencia parcial:** entre 35 % y 74 %.
- **Sin evidencia suficiente:** menos de 35 %.

Estos umbrales miden coincidencia de texto, no competencia profesional real.

## 6. Consultar al agente

Selecciona un CV y abre **Consulta al agente**. Puedes preguntar, por ejemplo:

- ¿Qué experiencia respalda el requisito de Python?
- ¿El CV menciona el título solicitado?
- ¿Qué requisitos no tienen evidencia suficiente?
- ¿En qué página aparece la experiencia relevante?

El campo de consulta permanece arriba y el historial se muestra debajo. Cambiar de candidato limpia el contexto para evitar mezclar CV.

Sin API key, el agente devuelve fragmentos locales. Con Gemini u Ollama, redacta una respuesta usando únicamente el perfil y el CV seleccionado. El chat no modifica el ranking.

## 7. Criterios sensibles

TalentIA excluye del puntaje requisitos relacionados con edad, género, estado civil, nacionalidad, religión, embarazo, discapacidad, fotografía, raza, etnia u orientación sexual. Si detecta uno, muestra una advertencia para revisión humana y legal.

La lista es una protección técnica básica, no asesoría legal. El equipo debe aplicar la legislación y política de selección correspondientes.

## 8. Privacidad

- Los PDF y el OCR se procesan localmente.
- Los archivos, vectores, nombres de candidatos, preguntas y respuestas no se persisten en el flujo de RR. HH.
- Si Gemini está activo, la búsqueda previa es local y solo se envían fragmentos recuperados del perfil y del CV seleccionado.
- No uses una clave API compartida ni la publiques en GitHub.
- Para demostraciones, utiliza datos ficticios.

## 9. Problemas frecuentes

### No aparecen criterios

El perfil debe indicar de forma explícita requisitos de experiencia, formación, título, certificación, conocimientos o habilidades. La aplicación no inventa criterios.

### Un CV muestra error y los demás sí aparecen

El error se aísla por archivo. Revisa que ese PDF no esté vacío, dañado o protegido con contraseña. Si es un escaneo, vuelve a cargar el lote usando OCR.

### El OCR tarda

Cada página se convierte en imagen y se reconoce localmente. Reduce la cantidad de CV o usa el modo Normal cuando el texto sea seleccionable.

### El puerto 8501 está ocupado

```powershell
python -m streamlit run ats_frontend/streamlit_app.py --server.port 8502
```

### Gemini no responde

El ranking seguirá funcionando. Retira la clave para usar el modo local o activa Ollama si está instalado.
