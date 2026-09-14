# Criterios de aceptacion — SPEC-031

**Caracteristica:** runtime unico de TalentIA.

## AC-001 — Arranque unico

**Cubre:** FR-001, NFR-001

```gherkin
Escenario: ejecutar el piloto
  Dado un entorno Python 3.12 con el paquete instalado
  Cuando se inicia el entrypoint documentado
  Entonces responde `talentia.main:app` y no se inicia Streamlit ni la API heredada
```

**Evidencia requerida:** import del ASGI app, prueba `/health` e instrucciones reproducibles.

## AC-002 — Legado fuera del producto

**Cubre:** FR-002, SEC-002

```gherkin
Escenario: inspeccionar el arbol mantenido
  Dado el repositorio consolidado
  Cuando se buscan imports y entrypoints heredados
  Entonces no existen consumidores ni servicios activos de esos paquetes
```

**Evidencia requerida:** busqueda global y verificador de repositorio.

## AC-003 — Dependencias minimas

**Cubre:** FR-003, NFR-001

```gherkin
Escenario: instalar el piloto
  Dado un entorno Python limpio
  Cuando se instalan las dependencias oficiales
  Entonces no se requieren Streamlit, FAISS, OCR heredado, LangChain ni MLflow
```

**Evidencia requerida:** metadatos del paquete, `pip check` y smoke de importacion.

## AC-004 — Migracion y regresion

**Cubre:** FR-004, NFR-002, NFR-003, SEC-001

```gherkin
Escenario: verificar la consolidacion
  Dado una base vacia y el tag de respaldo
  Cuando se ejecutan migraciones y controles de calidad
  Entonces la migracion llega a head y todas las pruebas greenfield pasan
```

**Evidencia requerida:** Alembic, pytest, Ruff, formato, mypy y referencia del tag.
