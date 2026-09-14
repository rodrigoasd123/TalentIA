import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROYECTO / "src"))

from sqlalchemy import func, select  # noqa: E402

from talentia.config import cargar_configuracion  # noqa: E402
from talentia.modules.access.domain.modelos import PERMISOS_POR_ROL, Rol  # noqa: E402
from talentia.platform.security.contrasenas import hash_contrasena  # noqa: E402
from talentia.shared.domain.modelos import nuevo_id  # noqa: E402
from talentia.shared.infrastructure.base_datos import (  # noqa: E402
    FabricaSesiones,
    crear_motor,
)
from talentia.shared.infrastructure.modelos_orm import (  # noqa: E402
    AsignacionUsuarioClienteModelo,
    CandidatoModelo,
    ClienteModelo,
    DocumentoCandidatoModelo,
    EvaluacionModelo,
    PerfilPuestoModelo,
    PostulacionModelo,
    RolModelo,
    UsuarioModelo,
    UsuarioRolModelo,
    VersionPerfilPuestoModelo,
)


def run_seed():  # noqa: C901
    configuracion = cargar_configuracion()
    motor = crear_motor(configuracion.url_base_datos)
    fabrica = FabricaSesiones(motor)

    with fabrica.sesion() as sesion:
        # 1. Cliente TCS
        cliente = sesion.scalar(select(ClienteModelo).where(ClienteModelo.codigo == "TCS"))
        if not cliente:
            cliente = ClienteModelo(
                id=nuevo_id(), codigo="TCS", nombre="Tata Consultancy Services (TCS)", activo=True
            )
            sesion.add(cliente)
            sesion.flush()

        # 2. Roles del sistema
        roles = {}
        for rol, permisos in PERMISOS_POR_ROL.items():
            r_obj = sesion.scalar(select(RolModelo).where(RolModelo.codigo == rol))
            if not r_obj:
                r_obj = RolModelo(id=nuevo_id(), codigo=rol, permisos=sorted(permisos))
                sesion.add(r_obj)
                sesion.flush()
            roles[Rol(rol)] = r_obj

        # 3. Usuarios de Laboratorio
        clave_lab = "Laboratorio-TalentIA-2026!"
        hash_lab = hash_contrasena(clave_lab)

        usuarios_data = [
            ("admin@ejemplo.local", "Administrador Principal", Rol.ADMINISTRADOR),
            ("reclutador@ejemplo.local", "Reclutador Senior", Rol.RECLUTADOR),
            ("gestor@ejemplo.local", "Gestor de Contratacion", Rol.GESTOR_CONTRATACION),
            ("auditor@ejemplo.local", "Auditor de Cumplimiento", Rol.AUDITOR),
            ("entrevistador@ejemplo.local", "Entrevistador Tecnico", Rol.ENTREVISTADOR),
            ("importador@ejemplo.local", "Operador de Lotes", Rol.IMPORTADOR),
        ]

        for correo, nombre, rol in usuarios_data:
            usr = sesion.scalar(select(UsuarioModelo).where(UsuarioModelo.correo == correo))
            if not usr:
                usr = UsuarioModelo(
                    id=nuevo_id(),
                    correo=correo,
                    nombre=nombre,
                    hash_contrasena=hash_lab,
                    activo=True,
                )
                sesion.add(usr)
                sesion.flush()
                sesion.add(UsuarioRolModelo(usuario_id=usr.id, rol_id=roles[rol].id))
                sesion.add(AsignacionUsuarioClienteModelo(usuario_id=usr.id, cliente_id=cliente.id))
            else:
                usr.hash_contrasena = hash_lab
                usr.activo = True

        sesion.flush()

        # 4. Convocatorias (Perfiles de Puesto)
        convocatorias_def = [
            {
                "codigo": "CONV-2026-001",
                "titulo": "Desarrollador Fullstack Senior (Python / React)",
                "ctc": Decimal("12500.00"),
                "requisitos": [
                    {
                        "codigo": "EXP-PY",
                        "descripcion": "Minimo 5 anos de experiencia en Python y FastAPI/Django",
                        "obligatorio": True,
                        "peso": "3",
                    },
                    {
                        "codigo": "EXP-REACT",
                        "descripcion": "Experiencia solida en React, TypeScript y Redux/Zustand",
                        "obligatorio": True,
                        "peso": "2",
                    },
                    {
                        "codigo": "BD-SQL",
                        "descripcion": (
                            "Diseno y optimizacion de modelos relacionales PostgreSQL/MySQL"
                        ),
                        "obligatorio": True,
                        "peso": "2",
                    },
                    {
                        "codigo": "DOCKER-CLOUD",
                        "descripcion": "Contenedores Docker y despliegue en entornos AWS o GCP",
                        "obligatorio": False,
                        "peso": "1",
                    },
                ],
            },
            {
                "codigo": "CONV-2026-002",
                "titulo": "Ingeniero de Datos Mid (Data y Analytics)",
                "ctc": Decimal("9800.00"),
                "requisitos": [
                    {
                        "codigo": "EXP-SQL-AVZ",
                        "descripcion": "SQL avanzado y optimizacion de consultas analiticas y CTEs",
                        "obligatorio": True,
                        "peso": "3",
                    },
                    {
                        "codigo": "ETL-PY",
                        "descripcion": "Desarrollo de pipelines ETL/ELT con Python y Pandas/Polars",
                        "obligatorio": True,
                        "peso": "3",
                    },
                    {
                        "codigo": "SPARK-AIRFLOW",
                        "descripcion": (
                            "Orquestacion con Apache Airflow y procesamiento distribuido"
                        ),
                        "obligatorio": False,
                        "peso": "2",
                    },
                    {
                        "codigo": "DATA-WAREHOUSE",
                        "descripcion": "Modelado dimensional en Snowflake, Databricks o BigQuery",
                        "obligatorio": False,
                        "peso": "1",
                    },
                ],
            },
            {
                "codigo": "CONV-2026-003",
                "titulo": "Lider de QA Automation y Testing",
                "ctc": Decimal("11000.00"),
                "requisitos": [
                    {
                        "codigo": "QA-AUTO",
                        "descripcion": "Automatizacion de pruebas E2E con Cypress o Playwright",
                        "obligatorio": True,
                        "peso": "3",
                    },
                    {
                        "codigo": "QA-API",
                        "descripcion": "Pruebas de integracion de APIs REST con Postman y Pytest",
                        "obligatorio": True,
                        "peso": "3",
                    },
                    {
                        "codigo": "CI-CD-QA",
                        "descripcion": (
                            "Integracion de suites de pruebas automaticas en GitHub Actions"
                        ),
                        "obligatorio": True,
                        "peso": "2",
                    },
                    {
                        "codigo": "CERT-ISTQB",
                        "descripcion": (
                            "Certificacion ISTQB o formacion formal en calidad de software"
                        ),
                        "obligatorio": False,
                        "peso": "1",
                    },
                ],
            },
        ]

        perfiles_map = {}
        versiones_map = {}

        for c_def in convocatorias_def:
            perf = sesion.scalar(
                select(PerfilPuestoModelo).where(
                    PerfilPuestoModelo.cliente_id == cliente.id,
                    PerfilPuestoModelo.codigo == c_def["codigo"],
                )
            )
            if not perf:
                perf = PerfilPuestoModelo(
                    id=nuevo_id(),
                    cliente_id=cliente.id,
                    codigo=c_def["codigo"],
                    titulo=c_def["titulo"],
                    activo=True,
                )
                sesion.add(perf)
                sesion.flush()

                v_perf = VersionPerfilPuestoModelo(
                    id=nuevo_id(),
                    perfil_id=perf.id,
                    numero=1,
                    requisitos=c_def["requisitos"],
                    ctc=c_def["ctc"],
                    publicado=True,
                )
                sesion.add(v_perf)
                sesion.flush()
            else:
                v_perf = sesion.scalar(
                    select(VersionPerfilPuestoModelo).where(
                        VersionPerfilPuestoModelo.perfil_id == perf.id,
                        VersionPerfilPuestoModelo.numero == 1,
                    )
                )
            perfiles_map[c_def["codigo"]] = perf
            versiones_map[c_def["codigo"]] = v_perf

        # 5. Candidatos (25 Postulantes)
        candidatos_raw = [
            (
                "Carlos",
                "Mendoza Ramos",
                "45871234",
                "carlos.mendoza@email.com",
                "+51987654321",
                "Lima, Peru",
                "LinkedIn",
                "Python, FastAPI, Django, React, Docker, AWS",
                Decimal("12000.00"),
                "CONV-2026-001",
                "oferta",
            ),
            (
                "Lucia",
                "Vargas Silva",
                "46982345",
                "lucia.vargas@email.com",
                "+51981234567",
                "Lima, Peru",
                "Computrabajo",
                "Python, React, TypeScript, PostgreSQL, CI/CD",
                Decimal("11500.00"),
                "CONV-2026-001",
                "entrevista",
            ),
            (
                "Diego",
                "Alarcon Castro",
                "47123456",
                "diego.alarcon@email.com",
                "+51976543210",
                "Arequipa, Peru",
                "Referido",
                "FastAPI, Vue.js, Node.js, SQLite, Redis",
                Decimal("10500.00"),
                "CONV-2026-001",
                "revision_humana",
            ),
            (
                "Valeria",
                "Gutierrez Pena",
                "48234567",
                "valeria.gutierrez@email.com",
                "+51965432109",
                "Lima, Peru",
                "LinkedIn",
                "Python, Django, React, Redux, Docker",
                Decimal("11000.00"),
                "CONV-2026-001",
                "en_evaluacion",
            ),
            (
                "Martin",
                "Rojas Paredes",
                "49345678",
                "martin.rojas@email.com",
                "+51954321098",
                "Trujillo, Peru",
                "Bumeran",
                "Python backend, Flask, REST APIs, MySQL",
                Decimal("9500.00"),
                "CONV-2026-001",
                "cv_recibido",
            ),
            (
                "Andrea",
                "Flores Quiroz",
                "50456789",
                "andrea.flores@email.com",
                "+51943210987",
                "Lima, Peru",
                "LinkedIn",
                "React, TypeScript, Next.js, Python basico",
                Decimal("9000.00"),
                "CONV-2026-001",
                "nueva",
            ),
            (
                "Jorge",
                "Navarro Salgado",
                "51567890",
                "jorge.navarro@email.com",
                "+51932109876",
                "Cusco, Peru",
                "Computrabajo",
                "Fullstack Python, JavaScript, MongoDB",
                Decimal("8800.00"),
                "CONV-2026-001",
                "nueva",
            ),
            (
                "Mariana",
                "Salazar Benitez",
                "52678901",
                "mariana.salazar@email.com",
                "+51921098765",
                "Lima, Peru",
                "LinkedIn",
                "FastAPI, React, Kubernetes, AWS Lambda",
                Decimal("13000.00"),
                "CONV-2026-001",
                "entrevista",
            ),
            (
                "Sebastian",
                "Herrera Medina",
                "53789012",
                "sebastian.herrera@email.com",
                "+51910987654",
                "Lima, Peru",
                "LinkedIn",
                "SQL avanzado, Python, Pandas, Airflow, Snowflake",
                Decimal("9500.00"),
                "CONV-2026-002",
                "oferta",
            ),
            (
                "Camila",
                "Caceres Torres",
                "54890123",
                "camila.caceres@email.com",
                "+51909876543",
                "Arequipa, Peru",
                "Referido",
                "ETL pipelines, Spark, Python, BigQuery",
                Decimal("9200.00"),
                "CONV-2026-002",
                "entrevista",
            ),
            (
                "Rodrigo",
                "Paredes Loyola",
                "55901234",
                "rodrigo.paredes@email.com",
                "+51998765432",
                "Lima, Peru",
                "Computrabajo",
                "Python, SQL, PostgreSQL, Databricks, PowerBI",
                Decimal("8900.00"),
                "CONV-2026-002",
                "revision_humana",
            ),
            (
                "Gabriela",
                "Vega Morales",
                "56012345",
                "gabriela.vega@email.com",
                "+51987654320",
                "Lima, Peru",
                "LinkedIn",
                "Airflow, Python, Data modeling, Redshift",
                Decimal("9400.00"),
                "CONV-2026-002",
                "en_evaluacion",
            ),
            (
                "Mateo",
                "Campos Zuniga",
                "57123450",
                "mateo.campos@email.com",
                "+51976543219",
                "Chiclayo, Peru",
                "Bumeran",
                "SQL Server, Python ETL, SSIS, Reporting",
                Decimal("7800.00"),
                "CONV-2026-002",
                "cv_recibido",
            ),
            (
                "Sofia",
                "Castillo Rivas",
                "58234561",
                "sofia.castillo@email.com",
                "+51965432108",
                "Lima, Peru",
                "LinkedIn",
                "Python, Pandas, Polars, Docker, GCP",
                Decimal("8500.00"),
                "CONV-2026-002",
                "nueva",
            ),
            (
                "Alejandro",
                "Bustamante Diaz",
                "59345672",
                "alejandro.bustamante@email.com",
                "+51954321097",
                "Trujillo, Peru",
                "Computrabajo",
                "Data Analytics, SQL, Tableau, Python",
                Decimal("7500.00"),
                "CONV-2026-002",
                "nueva",
            ),
            (
                "Daniela",
                "Ortiz Solano",
                "60456783",
                "daniela.ortiz@email.com",
                "+51943210986",
                "Lima, Peru",
                "LinkedIn",
                "Apache Spark, Airflow, Python, AWS Glue",
                Decimal("10000.00"),
                "CONV-2026-002",
                "en_evaluacion",
            ),
            (
                "Felipe",
                "Montoya Prado",
                "61567894",
                "felipe.montoya@email.com",
                "+51932109875",
                "Lima, Peru",
                "LinkedIn",
                "Cypress, Playwright, Pytest, CI/CD, ISTQB",
                Decimal("11200.00"),
                "CONV-2026-003",
                "entrevista",
            ),
            (
                "Patricia",
                "Leon Valenzuela",
                "62678905",
                "patricia.leon@email.com",
                "+51921098764",
                "Arequipa, Peru",
                "Referido",
                "Selenium, Pytest, REST API testing, Postman",
                Decimal("9800.00"),
                "CONV-2026-003",
                "revision_humana",
            ),
            (
                "Renato",
                "Chavez Aguirre",
                "63789016",
                "renato.chavez@email.com",
                "+51910987653",
                "Lima, Peru",
                "LinkedIn",
                "Playwright, TypeScript, GitHub Actions, Docker",
                Decimal("10500.00"),
                "CONV-2026-003",
                "revision_humana",
            ),
            (
                "Natalia",
                "Vasquez Romero",
                "64890127",
                "natalia.vasquez@email.com",
                "+51909876542",
                "Lima, Peru",
                "Computrabajo",
                "QA manual, Cypress inicial, Postman, Jira",
                Decimal("8000.00"),
                "CONV-2026-003",
                "en_evaluacion",
            ),
            (
                "Gonzalo",
                "Espinoza Bravo",
                "65901238",
                "gonzalo.espinoza@email.com",
                "+51998765431",
                "Piura, Peru",
                "Bumeran",
                "Selenium WebDriver, Java, Pytest, Jenkins",
                Decimal("8500.00"),
                "CONV-2026-003",
                "cv_recibido",
            ),
            (
                "Fiorella",
                "Ponce Hurtado",
                "66012349",
                "fiorella.ponce@email.com",
                "+51987654329",
                "Lima, Peru",
                "LinkedIn",
                "QA Automation, Cypress, Karate, JMeter",
                Decimal("9200.00"),
                "CONV-2026-003",
                "cv_recibido",
            ),
            (
                "Emilio",
                "Cruz Palacios",
                "67123451",
                "emilio.cruz@email.com",
                "+51976543218",
                "Trujillo, Peru",
                "Computrabajo",
                "Manual testing, SQL verification, Postman",
                Decimal("6500.00"),
                "CONV-2026-003",
                "nueva",
            ),
            (
                "Ximena",
                "Delgado Barreto",
                "68234562",
                "ximena.delgado@email.com",
                "+51965432107",
                "Lima, Peru",
                "LinkedIn",
                "Playwright, Python, API Automation, Pytest",
                Decimal("10200.00"),
                "CONV-2026-003",
                "cv_recibido",
            ),
            (
                "Esteban",
                "Reyes Miranda",
                "69345673",
                "esteban.reyes@email.com",
                "+51954321096",
                "Arequipa, Peru",
                "Referido",
                "Cypress, JavaScript, CI/CD, Git, ISTQB CTFL",
                Decimal("9500.00"),
                "CONV-2026-003",
                "en_evaluacion",
            ),
        ]

        candidatos_creados = 0
        postulaciones_creadas = 0
        documentos_creados = 0

        for (
            nombres,
            apellidos,
            dni,
            correo,
            tel,
            ubi,
            fuente,
            skills,
            sueldo,
            cod_conv,
            estado_post,
        ) in candidatos_raw:
            cand = sesion.scalar(
                select(CandidatoModelo).where(
                    CandidatoModelo.cliente_id == cliente.id,
                    CandidatoModelo.documento_normalizado == dni,
                )
            )
            if not cand:
                cand = CandidatoModelo(
                    id=nuevo_id(),
                    cliente_id=cliente.id,
                    nombres=nombres,
                    apellidos=apellidos,
                    tipo_documento="DNI",
                    documento_normalizado=dni,
                    correo=correo,
                    telefono=tel,
                    fecha_nacimiento=date(1993, 5, 15),
                    ubicacion=ubi,
                    fuente=fuente,
                    reclutador="Reclutador Senior",
                    perfil_solicitado=perfiles_map[cod_conv].titulo,
                    conocimiento_tecnico=skills,
                    disponibilidad="Inmediata",
                    expectativa_salarial=sueldo,
                    ctc_rol=sueldo,
                    estado="en_proceso",
                    etiquetas=["laboratorio", cod_conv.lower()],
                )
                sesion.add(cand)
                sesion.flush()
                candidatos_creados += 1

            # 6. Postulacion
            v_perf = versiones_map[cod_conv]
            post = sesion.scalar(
                select(PostulacionModelo).where(
                    PostulacionModelo.candidato_id == cand.id,
                    PostulacionModelo.version_perfil_id == v_perf.id,
                )
            )
            if not post:
                post = PostulacionModelo(
                    id=nuevo_id(),
                    cliente_id=cliente.id,
                    candidato_id=cand.id,
                    version_perfil_id=v_perf.id,
                    fuente=fuente.lower(),
                    estado=estado_post,
                    clave_idempotencia=f"post-{cand.id}-{v_perf.id}",
                )
                sesion.add(post)
                sesion.flush()
                postulaciones_creadas += 1

            # 7. Documento CV (para los primeros 15 candidatos)
            if candidatos_creados <= 15:
                doc_hash = f"hash-{cand.id}-cv-sha256"
                doc = sesion.scalar(
                    select(DocumentoCandidatoModelo).where(
                        DocumentoCandidatoModelo.candidato_id == cand.id,
                        DocumentoCandidatoModelo.hash_sha256 == doc_hash,
                    )
                )
                if not doc:
                    doc = DocumentoCandidatoModelo(
                        id=nuevo_id(),
                        cliente_id=cliente.id,
                        candidato_id=cand.id,
                        nombre_original=f"CV_{nombres}_{apellidos.split()[0]}.pdf",
                        tipo_mime="application/pdf",
                        hash_sha256=doc_hash,
                        ruta_almacenamiento=f"storage/greenfield/cvs/{cand.id}.pdf",
                        tamano_bytes=1024 * 350,
                    )
                    sesion.add(doc)
                    sesion.flush()
                    documentos_creados += 1

                    # Si el estado es oferta o entrevista, agregar evaluacion de ejemplo
                    if estado_post in {"oferta", "entrevista"}:
                        evaluacion = EvaluacionModelo(
                            id=nuevo_id(),
                            cliente_id=cliente.id,
                            postulacion_id=post.id,
                            documento_id=doc.id,
                            version_perfil_id=v_perf.id,
                            puntaje_documental=Decimal("88.50"),
                            requiere_revision=False,
                            modelo="gpt-5.4-mini",
                            version_prompt="v1.0",
                            simulada=False,
                        )
                        sesion.add(evaluacion)
                        sesion.flush()

        sesion.commit()

        cands_total = sesion.scalar(select(func.count()).select_from(CandidatoModelo))
        posts_total = sesion.scalar(select(func.count()).select_from(PostulacionModelo))
        docs_total = sesion.scalar(select(func.count()).select_from(DocumentoCandidatoModelo))
        evals_total = sesion.scalar(select(func.count()).select_from(EvaluacionModelo))

        print("=== Siembra Greenfield Completada ===")
        print(f"Usuarios de laboratorio: {len(usuarios_data)}")
        print(f"Convocatorias activas: {len(convocatorias_def)}")
        print(f"Candidatos totales: {cands_total}")
        print(f"Postulaciones totales: {posts_total}")
        print(f"Documentos CV: {docs_total}")
        print(f"Evaluaciones: {evals_total}")


if __name__ == "__main__":
    run_seed()
