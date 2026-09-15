from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from talentia.modules.recruitment.application.extractor_convocatoria import (
    extraer_bases_convocatoria,
    parsear_texto_convocatoria,
)
from talentia.web.routes.paginas import _requisitos_desde_texto


def _crear_docx_simple(*lineas: str) -> bytes:
    parrafos = "".join(f"<w:p><w:r><w:t>{linea}</w:t></w:r></w:p>" for linea in lineas)
    documento = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{parrafos}</w:body></w:document>"
    )
    contenido = BytesIO()
    with ZipFile(contenido, "w", ZIP_DEFLATED) as archivo:
        archivo.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archivo.writestr("word/document.xml", documento)
    return contenido.getvalue()


def _sesion_web(cliente_api: dict[str, object]) -> tuple[object, str]:
    cliente = cliente_api["cliente"]
    token = str(cliente_api["cabeceras"]["Authorization"]).removeprefix("Bearer ")
    cliente.cookies.set("talentia_session", token)
    csrf = str(cliente.app.state.firmador.leer(token)["csrf"])
    return cliente, csrf


def test_extraer_convocatoria_formato_tcs_corporativo() -> None:
    texto_tcs = """
TATA CONSULTANCY SERVICES
FORMATO DE REQUERIMIENTO DE PERSONAL

Nombre del Rol: Developer Java Microservicios APIS Principiante Avanzado - Medium
Número de Vacantes: 1

Funciones o Tareas
Experiencia Técnica:
• Fuertes habilidades en programación funcional y OOP con Java 11 a más.
• Experiencia en programación con Springboot, Spring-core, Spring-mvc, Spring-data.
• Conocimiento con programación reactiva con RxJava, Reactor o WebFlux.
• Experiencia de 3 años en desarrollo de servicios RESTful API y OpenAPI/Swagger.
• Experiencia en seguridad JWT, OAuth2, Certificados, PKI, Vault.
• Experiencia utilizando Unit and Integration Testing con JUnit y Mockito.
• Experiencia utilizando Git, GitHub o Bitbucket.
• Experiencia con Jenkins, a nivel básico.
• Experiencia en base de datos relacionales con Sql Server y Azure SQL.
• Metodología ágil con SCRUM.

Deseable:
• Despliegue con contenedores Dockers y Kubernetes.
• Conocimiento en Quarkus y mensajería con Apache Kafka.
• Conocimiento en base de datos no-relacionales como CosmosDB o MongoDB.
• Conocimientos en Cloud Azure (App Service, Functions, Blob Storage).

Necesario:
• Experiencia comprobada en proyectos de desarrollo corporativos.
"""
    res = parsear_texto_convocatoria(texto_tcs)

    assert "Developer Java Microservicios" in res.titulo
    assert res.total_obligatorios >= 10
    assert res.total_deseables >= 4
    assert len(res.requisitos) >= 14

    # Verificar que el formato sea parseable por la validación de dominio de TalentIA
    reqs_validados = _requisitos_desde_texto(res.requisitos_texto)
    assert len(reqs_validados) == len(res.requisitos)

    # Verificar que las líneas obligatorias y opcionales estén bien etiquetadas
    lineas = res.requisitos_texto.splitlines()
    obligatorios = [l for l in lineas if " | obligatorio | " in l]
    opcionales = [l for l in lineas if " | opcional | " in l]
    assert len(obligatorios) == res.total_obligatorios
    assert len(opcionales) == res.total_deseables


def test_extraer_convocatoria_formato_estandar_con_ctc() -> None:
    docx_bytes = _crear_docx_simple(
        "Desarrollador Backend Senior (Python / Cloud)",
        "Código: DEV-BACK-01 | Cliente: Tata Consultancy Services (TCS)",
        "Compensación Total (CTC): S/ 8,500.00 mensuales",
        "Modalidad: Híbrido / Remoto (Perú)",
        "1. Descripción del Puesto",
        "Estamos en la búsqueda de un Desarrollador Backend Senior.",
        "2. Requisitos Obligatorios",
        "• [REQ-PY-01] Experiencia sólida en Python (FastAPI o Django) (Ponderación: 2.5)",
        "• [REQ-SQL-02] Bases de datos relacionales SQL (PostgreSQL) (Ponderación: 2.0)",
        "• [REQ-CLOUD-03] Contenedores Docker y despliegue en nube (AWS) (Ponderación: 2.0)",
        "3. Requisitos Deseables",
        "• [REQ-API-04] Diseño de APIs RESTful y microservicios (Ponderación: 1.5)",
        "• [REQ-TEST-05] Pruebas unitarias e integración con Pytest (Ponderación: 1.0)",
    )

    res = extraer_bases_convocatoria(
        docx_bytes,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        nombre_archivo="DEV-BACK-01.docx",
    )

    assert res.codigo == "DEV-BACK-01"
    assert res.ctc == "8500.00"
    assert res.total_obligatorios == 3
    assert res.total_deseables == 2
    assert "REQ-PY-01 | Experiencia sólida en Python (FastAPI o Django) | obligatorio | 2.5" in res.requisitos_texto
    assert "REQ-API-04 | Diseño de APIs RESTful y microservicios | opcional | 1.5" in res.requisitos_texto


def test_endpoint_analizar_convocatoria_flujo_web(cliente_api) -> None:
    cliente, csrf = _sesion_web(cliente_api)

    # 1. Crear perfil base
    resp_perfil = cliente.post(
        "/perfiles/nuevo",
        data={
            "csrf": csrf,
            "cliente_id": cliente_api["cliente_id"],
            "codigo": "DEV-CONV-TEST",
            "titulo": "Desarrollador Java y Cloud de Prueba",
        },
    )
    assert resp_perfil.status_code in {200, 303}

    # Obtener el perfil
    from sqlalchemy import text
    with cliente.app.state.servicio._fabrica() as unidad:
        row = unidad.datos.sesion.execute(
            text("SELECT id FROM job_profiles WHERE codigo = 'DEV-CONV-TEST'")
        ).first()
        perfil_id = row[0]

    # 2. Generar archivo docx de convocatoria
    docx_bytes = _crear_docx_simple(
        "Nombre del Rol: Ingeniero Java Spring Cloud",
        "Código: JAVA-CLOUD-99",
        "Compensación Total (CTC): S/ 9,000.00",
        "Experiencia Técnica:",
        "• Dominio de Java 17 y Spring Boot 3",
        "• Microservicios con Docker y Kafka",
        "Deseable:",
        "• Certificación en AWS o GCP",
    )

    # 3. Probar endpoint AJAX /analizar-convocatoria
    resp_analisis = cliente.post(
        f"/perfiles/{perfil_id}/versiones/analizar-convocatoria",
        data={"csrf": csrf},
        files=[(
            "archivo",
            ("convocatoria_java.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        )],
    )
    assert resp_analisis.status_code == 200
    data = resp_analisis.json()
    assert data["exito"] is True
    assert data["ctc"] == "9000.00"
    assert data["total_obligatorios"] >= 2
    assert data["total_deseables"] >= 1
    assert "obligatorio" in data["requisitos_texto"]
    assert "opcional" in data["requisitos_texto"]

    # 4. Guardar la versión con los requisitos autocompletados
    resp_guardar = cliente.post(
        f"/perfiles/{perfil_id}/versiones/nueva",
        data={
            "csrf": csrf,
            "requisitos_texto": data["requisitos_texto"],
            "ctc": data["ctc"],
            "publicado": "si",
        },
    )
    assert resp_guardar.status_code in {200, 303}

    # 5. Comprobar que la versión y requisitos existen en la vacante
    resp_vacante = cliente.get(f"/perfiles/{perfil_id}")
    assert resp_vacante.status_code == 200
    assert "Dominio de Java 17" in resp_vacante.text
    assert "Microservicios con Docker y Kafka" in resp_vacante.text
    assert "S/ 9,000.00" in resp_vacante.text


def test_endpoint_analizar_convocatoria_previa(cliente_api) -> None:
    cliente, csrf = _sesion_web(cliente_api)

    docx_bytes = _crear_docx_simple(
        "Nombre del Rol: QA Lead Automation Specialist",
        "Experiencia Técnica:",
        "• Experiencia en Cypress y Playwright",
    )

    resp = cliente.post(
        "/perfiles/analizar-convocatoria-previa",
        data={"csrf": csrf},
        files=[(
            "archivo",
            ("jd_qa.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        )],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exito"] is True
    assert "QA Lead Automation" in data["titulo"]
    assert data["total_requisitos"] >= 1


def test_crear_perfil_con_convocatoria_directo_en_paso_1(cliente_api) -> None:
    cliente, csrf = _sesion_web(cliente_api)
    docx_bytes = _crear_docx_simple(
        "Nombre del Rol: Ingeniero DevOps Kubernetes Cloud",
        "Código: DEVOPS-K8S-01",
        "Compensación Total (CTC): S/ 11,000.00",
        "Experiencia Técnica:",
        "• Experiencia con clústeres EKS y Terraform",
        "Deseable:",
        "• Certificación CKA",
    )
    resp = cliente.post(
        "/perfiles/nuevo",
        data={
            "csrf": csrf,
            "cliente_id": cliente_api["cliente_id"],
            "codigo": "",
            "titulo": "",
        },
        files=[("archivo_convocatoria", ("devops.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
    )
    assert resp.status_code in {200, 303}
    # Verificamos que redirige directamente a la vacante ya publicada con sus requisitos
    assert "versiones/nueva" not in str(resp.url)
    assert "Ingeniero DevOps Kubernetes Cloud" in resp.text or "DEVOPS-K8S-01" in resp.text


def test_version_con_archivo_adjunto_sin_escribir_requisitos(cliente_api) -> None:
    cliente, csrf = _sesion_web(cliente_api)
    # 1. Crear perfil manual
    resp_perfil = cliente.post(
        "/perfiles/nuevo",
        data={
            "csrf": csrf,
            "cliente_id": cliente_api["cliente_id"],
            "codigo": "FRONT-TEST-01",
            "titulo": "Frontend Engineer Test",
        },
    )
    assert resp_perfil.status_code in {200, 303}
    from sqlalchemy import text
    with cliente.app.state.servicio._fabrica() as unidad:
        row = unidad.datos.sesion.execute(
            text("SELECT id FROM job_profiles WHERE codigo = 'FRONT-TEST-01'")
        ).first()
        perfil_id = row[0]

    # 2. Guardar versión subiendo archivo pero con textarea vacía (no debe salir error de campo requerido)
    docx_bytes = _crear_docx_simple(
        "Nombre del Rol: Frontend Specialist React",
        "Compensación Total (CTC): S/ 10,000.00",
        "Experiencia Técnica:",
        "• Dominio de React 18 y TypeScript",
        "Deseable:",
        "• Next.js y Tailwind",
    )
    resp_version = cliente.post(
        f"/perfiles/{perfil_id}/versiones/nueva",
        data={
            "csrf": csrf,
            "requisitos_texto": "", # Dejado vacío intencionalmente por el reclutador
            "ctc": "",
            "publicado": "si",
        },
        files=[("archivo_convocatoria", ("jd_frontend.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
    )
    assert resp_version.status_code in {200, 303}
    # Verificamos que la vacante quedó creada y contiene los requisitos del archivo
    resp_vacante = cliente.get(f"/perfiles/{perfil_id}")
    assert resp_vacante.status_code == 200
    assert "React 18" in resp_vacante.text
    assert "S/ 10,000.00" in resp_vacante.text
