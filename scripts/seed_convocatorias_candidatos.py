"""Genera 3 convocatorias completas y 25 postulantes con sus postulaciones."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from talentia.modules.candidates.domain.modelos import (
    normalizar_documento,
    ultimos_nueve_telefono,
)
from talentia.shared.domain.modelos import nuevo_id

DB_PATH = ROOT_DIR / "talentia_greenfield.db"


CONVOCATORIAS = [
    {
        "codigo": "DEV-BACK-01",
        "titulo": "Desarrollador Backend Senior (Python / Cloud)",
        "ctc": Decimal("8500.00"),
        "requisitos": [
            {
                "codigo": "REQ-PY-01",
                "descripcion": "Experiencia sólida en Python (FastAPI o Django) mínima de 4 años",
                "obligatorio": True,
                "peso": "2.5",
            },
            {
                "codigo": "REQ-SQL-02",
                "descripcion": "Bases de datos relacionales SQL (PostgreSQL / SQLite) y diseño de esquemas",
                "obligatorio": True,
                "peso": "2.0",
            },
            {
                "codigo": "REQ-CLOUD-03",
                "descripcion": "Contenedores Docker y despliegue en nube (AWS / GCP / Azure)",
                "obligatorio": True,
                "peso": "2.0",
            },
            {
                "codigo": "REQ-API-04",
                "descripcion": "Diseño de APIs RESTful, microservicios y patrones de arquitectura limpia",
                "obligatorio": False,
                "peso": "1.5",
            },
            {
                "codigo": "REQ-TEST-05",
                "descripcion": "Pruebas unitarias e integración con Pytest y pipelines CI/CD",
                "obligatorio": False,
                "peso": "1.0",
            },
        ],
    },
    {
        "codigo": "QA-AUTO-02",
        "titulo": "Ingeniero QA Automation (Web / API)",
        "ctc": Decimal("6800.00"),
        "requisitos": [
            {
                "codigo": "REQ-QA-01",
                "descripcion": "Experiencia en automatización de pruebas con Playwright, Cypress o Selenium",
                "obligatorio": True,
                "peso": "3.0",
            },
            {
                "codigo": "REQ-API-02",
                "descripcion": "Pruebas automatizadas de APIs REST con Postman o Pytest/Requests",
                "obligatorio": True,
                "peso": "2.5",
            },
            {
                "codigo": "REQ-CODE-03",
                "descripcion": "Lenguaje de programación para scripting (Python, TypeScript o JavaScript)",
                "obligatorio": True,
                "peso": "2.0",
            },
            {
                "codigo": "REQ-CICD-04",
                "descripcion": "Integración de suites de pruebas en GitHub Actions o Jenkins",
                "obligatorio": False,
                "peso": "1.5",
            },
            {
                "codigo": "REQ-ISTQB-05",
                "descripcion": "Certificación ISTQB Foundation Level o gestión de planes de prueba",
                "obligatorio": False,
                "peso": "1.0",
            },
        ],
    },
    {
        "codigo": "DATA-ENG-03",
        "titulo": "Ingeniero de Datos (ETL / Big Data / Analytics)",
        "ctc": Decimal("9200.00"),
        "requisitos": [
            {
                "codigo": "REQ-ETL-01",
                "descripcion": "Construcción y orquestación de pipelines de datos con Apache Airflow",
                "obligatorio": True,
                "peso": "3.0",
            },
            {
                "codigo": "REQ-PYSQL-02",
                "descripcion": "Python avanzado (Pandas/Polars) y SQL complejo para transformaciones de datos",
                "obligatorio": True,
                "peso": "2.5",
            },
            {
                "codigo": "REQ-DWH-03",
                "descripcion": "Modelado y consulta en Data Warehouses (Snowflake, BigQuery o Redshift)",
                "obligatorio": True,
                "peso": "2.5",
            },
            {
                "codigo": "REQ-SPARK-04",
                "descripcion": "Procesamiento distribuido de grandes volúmenes con PySpark / Databricks",
                "obligatorio": False,
                "peso": "1.5",
            },
            {
                "codigo": "REQ-GOV-05",
                "descripcion": "Gobierno de datos, linaje, calidad de datos y observabilidad de pipelines",
                "obligatorio": False,
                "peso": "0.5",
            },
        ],
    },
]

CANDIDATOS_DATOS = [
    ("Carlos Eduardo", "Mendoza Ramos", "45892147", "carlos.mendoza@gmail.com", "987451230", date(1993, 4, 12), "Miraflores, Lima", "LinkedIn", "Python, FastAPI, Docker, PostgreSQL, AWS", Decimal("8200.00"), "apto", 0),
    ("Valeria Sofia", "Chavez Quispe", "47123985", "valeria.chavez@outlook.com", "991245789", date(1996, 8, 24), "San Isidro, Lima", "Adecco", "Python, Django, Flask, Redis, CI/CD", Decimal("8000.00"), "en_proceso", 0),
    ("Mateo Alejandro", "Rios Fernandez", "43981245", "mateo.rios@gmail.com", "975841236", date(1990, 11, 3), "Surco, Lima", "Referido", "Python, FastAPI, Microservicios, Kubernetes", Decimal("9000.00"), "apto", 0),
    ("Camila Andrea", "Vargas Paredes", "48215478", "camila.vargas@hotmail.com", "982365147", date(1997, 2, 17), "San Miguel, Lima", "LinkedIn", "Python, SQLite, Git, Docker inicial", Decimal("7200.00"), "pendiente", 0),
    ("Diego Alonso", "Castro Morales", "42157896", "diego.castro@gmail.com", "964785123", date(1989, 7, 29), "Arequipa", "Computrabajo", "Python, Django, AWS Lambda, DynamoDB", Decimal("8500.00"), "en_proceso", 0),
    ("Luciana Beatriz", "Navarro Silva", "46985214", "luciana.navarro@gmail.com", "953214789", date(1995, 1, 9), "Jesus Maria, Lima", "Adecco", "FastAPI, PostgreSQL, SQLAlchemy, GCP", Decimal("8400.00"), "apto", 0),
    ("Gabriel Antonio", "Peralta Rojas", "41526398", "gabriel.peralta@yahoo.es", "984512369", date(1988, 12, 14), "Callao", "LinkedIn", "Python, Microservicios, RabbitMQ, Celery", Decimal("8700.00"), "respaldo", 0),
    ("Fiorella Ines", "Guzman Soto", "49321458", "fiorella.guzman@gmail.com", "971245896", date(1998, 5, 21), "Lince, Lima", "Portal TCS", "Python junior, APIs REST, MySQL", Decimal("6000.00"), "no_apto", 0),
    
    ("Rodrigo Martin", "Huaman Delgado", "44852179", "rodrigo.huaman@gmail.com", "986532147", date(1992, 9, 30), "Pueblo Libre, Lima", "LinkedIn", "Playwright, TypeScript, Pytest, Jenkins", Decimal("6700.00"), "apto", 1),
    ("Andrea Nicole", "Flores Cardenas", "47852369", "andrea.flores@outlook.com", "993214587", date(1996, 6, 15), "Magdalena, Lima", "Adecco", "Cypress, JavaScript, Postman, JMeter", Decimal("6500.00"), "en_proceso", 1),
    ("Joaquin Manuel", "Salazar Ruiz", "43698521", "joaquin.salazar@gmail.com", "974125896", date(1991, 3, 8), "Trujillo", "Computrabajo", "Selenium WebDriver, Python, Postman, CI/CD", Decimal("6800.00"), "apto", 1),
    ("Mariana Paz", "Cordova Nunez", "48521479", "mariana.cordova@hotmail.com", "981452369", date(1997, 10, 11), "Barranco, Lima", "LinkedIn", "Playwright, Postman, Cucumber BDD, ISTQB", Decimal("7000.00"), "respaldo", 1),
    ("Alonso Javier", "Mejia Herrera", "42987412", "alonso.mejia@gmail.com", "965874123", date(1990, 5, 4), "San Borja, Lima", "Referido", "QA Automation, Cypress, Playwright, Newman", Decimal("6800.00"), "contratado", 1),
    ("Daniela Rocio", "Alvarado Ponce", "46321478", "daniela.alvarado@gmail.com", "952147896", date(1994, 12, 19), "Los Olivos, Lima", "Adecco", "Selenium, TestNG, Java, Git", Decimal("6200.00"), "pendiente", 1),
    ("Sebastian David", "Cruz Balbuena", "41258963", "sebastian.cruz@outlook.com", "987412596", date(1987, 8, 2), "Chorrillos, Lima", "LinkedIn", "QA manual con nociones de Postman", Decimal("5500.00"), "no_apto", 1),
    ("Natalia Estefania", "Villanueva Leon", "49512368", "natalia.villanueva@gmail.com", "978541236", date(1998, 4, 18), "Surquillo, Lima", "Portal TCS", "Playwright, Python, GitHub Actions", Decimal("6600.00"), "en_proceso", 1),

    ("Bruno Emiliano", "Caceres Vega", "44125896", "bruno.caceres@gmail.com", "985214796", date(1991, 7, 23), "La Molina, Lima", "LinkedIn", "Airflow, Python, Snowflake, SQL, dbt", Decimal("9200.00"), "apto", 2),
    ("Patricia Elena", "Montesinos Barreda", "47258963", "patricia.montesinos@outlook.com", "994512368", date(1995, 9, 14), "San Isidro, Lima", "Adecco", "BigQuery, PySpark, Airflow, Python, GCP", Decimal("9000.00"), "en_proceso", 2),
    ("Gustavo Adolfo", "Espinoza Calderon", "43258741", "gustavo.espinoza@gmail.com", "976541238", date(1989, 2, 28), "Arequipa", "Computrabajo", "ETL pipelines, Databricks, Apache Spark, AWS", Decimal("9500.00"), "apto", 2),
    ("Adriana Lucia", "Benitez Cabrera", "48123654", "adriana.benitez@hotmail.com", "982145698", date(1996, 11, 7), "Miraflores, Lima", "LinkedIn", "Python, Pandas, SQL Server, PowerBI, ETL", Decimal("8000.00"), "pendiente", 2),
    ("Mauricio Renato", "Arce Gamboa", "42369852", "mauricio.arce@gmail.com", "963214587", date(1990, 8, 16), "Surco, Lima", "Referido", "Airflow, Redshift, AWS Glue, PySpark, Kafka", Decimal("9300.00"), "contratado", 2),
    ("Claudia Milagros", "Reyes Santillan", "46125478", "claudia.reyes@gmail.com", "951478523", date(1993, 10, 25), "Jesus Maria, Lima", "Adecco", "Data Engineering, Snowflake, SQL, Python, dbt", Decimal("8800.00"), "apto", 2),
    ("Christian Paul", "Zevallos Medina", "41587412", "christian.zevallos@yahoo.es", "984125639", date(1988, 6, 1), "Callao", "LinkedIn", "SQL avanzado, ETL Pentaho, Python básico", Decimal("7500.00"), "no_apto", 2),
    ("Lorena Marcela", "Tello Hurtado", "49125478", "lorena.tello@gmail.com", "972584163", date(1998, 1, 30), "San Borja, Lima", "Portal TCS", "Python, Airflow, BigQuery, Docker", Decimal("8900.00"), "en_proceso", 2),
    ("Ignacio Javier", "Osorio Bustamante", "45698741", "ignacio.osorio@outlook.com", "981254796", date(1992, 12, 5), "Pueblo Libre, Lima", "LinkedIn", "PySpark, AWS EMR, Airflow, SQL, DeltaLake", Decimal("9400.00"), "respaldo", 2),
]


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cliente_id = cur.execute("select id from clients where codigo='TCS'").fetchone()[0]

    versiones_ids: list[str] = []
    print("Creando o actualizando 3 convocatorias...")
    for conv in CONVOCATORIAS:
        existente = cur.execute(
            "select id from job_profiles where cliente_id=? and codigo=?",
            (cliente_id, conv["codigo"]),
        ).fetchone()

        if existente:
            perfil_id = existente[0]
            cur.execute(
                "update job_profiles set titulo=?, activo=1, actualizado_en=datetime('now') where id=?",
                (conv["titulo"], perfil_id),
            )
        else:
            perfil_id = nuevo_id()
            cur.execute(
                "insert into job_profiles (id, cliente_id, codigo, titulo, activo, version, creado_en, actualizado_en) values (?, ?, ?, ?, 1, 1, datetime('now'), datetime('now'))",
                (perfil_id, cliente_id, conv["codigo"], conv["titulo"]),
            )

        # Version 1 del perfil con requisitos
        v_existente = cur.execute(
            "select id from job_profile_versions where perfil_id=? and numero=1",
            (perfil_id,),
        ).fetchone()

        requisitos_json = json.dumps(conv["requisitos"])
        ctc_val = float(conv["ctc"])

        if v_existente:
            v_id = v_existente[0]
            cur.execute(
                "update job_profile_versions set requisitos=?, ctc=?, publicado=1, actualizado_en=datetime('now') where id=?",
                (requisitos_json, ctc_val, v_id),
            )
        else:
            v_id = nuevo_id()
            cur.execute(
                "insert into job_profile_versions (id, perfil_id, numero, requisitos, ctc, publicado, version, creado_en, actualizado_en) values (?, ?, 1, ?, ?, 1, 1, datetime('now'), datetime('now'))",
                (v_id, perfil_id, requisitos_json, ctc_val),
            )
        versiones_ids.append(v_id)
        print(f" - Convocatoria lista: {conv['codigo']} | {conv['titulo']} (Version ID: {v_id})")

    print("\nCreando 25 postulantes y sus postulaciones...")
    for i, c_data in enumerate(CANDIDATOS_DATOS):
        (
            nombres,
            apellidos,
            doc_raw,
            correo,
            tel_raw,
            f_nac,
            ubicacion,
            fuente,
            conocimiento,
            expectativa,
            estado,
            conv_idx,
        ) = c_data

        doc_norm = normalizar_documento(doc_raw)
        tel_norm = ultimos_nueve_telefono(tel_raw)
        version_perfil_id = versiones_ids[conv_idx]
        conv_codigo = CONVOCATORIAS[conv_idx]["codigo"]
        ctc_rol = float(CONVOCATORIAS[conv_idx]["ctc"])
        etiquetas_json = json.dumps([conv_codigo.lower(), estado, fuente.lower()])

        c_existente = cur.execute(
            "select id from candidates where cliente_id=? and documento_normalizado=?",
            (cliente_id, doc_norm),
        ).fetchone()

        if c_existente:
            cand_id = c_existente[0]
            cur.execute(
                """
                update candidates set
                    nombres=?, apellidos=?, tipo_documento='DNI', correo=?, telefono=?,
                    fecha_nacimiento=?, ubicacion=?, fuente=?, reclutador='Reclutador TCS',
                    perfil_solicitado=?, conocimiento_tecnico=?, disponibilidad='Inmediata',
                    expectativa_salarial=?, ctc_rol=?, estado=?, etiquetas=?,
                    actualizado_en=datetime('now')
                where id=?
                """,
                (
                    nombres,
                    apellidos,
                    correo,
                    tel_norm,
                    f_nac.isoformat(),
                    ubicacion,
                    fuente,
                    conv_codigo,
                    conocimiento,
                    float(expectativa),
                    ctc_rol,
                    estado,
                    etiquetas_json,
                    cand_id,
                ),
            )
        else:
            cand_id = nuevo_id()
            cur.execute(
                """
                insert into candidates (
                    id, cliente_id, nombres, apellidos, tipo_documento, documento_normalizado,
                    correo, telefono, fecha_nacimiento, ubicacion, fuente, reclutador,
                    perfil_solicitado, conocimiento_tecnico, disponibilidad, expectativa_salarial,
                    ctc_rol, estado, etiquetas, version, creado_en, actualizado_en
                ) values (?, ?, ?, ?, 'DNI', ?, ?, ?, ?, ?, ?, 'Reclutador TCS', ?, ?, 'Inmediata', ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                """,
                (
                    cand_id,
                    cliente_id,
                    nombres,
                    apellidos,
                    doc_norm,
                    correo,
                    tel_norm,
                    f_nac.isoformat(),
                    ubicacion,
                    fuente,
                    conv_codigo,
                    conocimiento,
                    float(expectativa),
                    ctc_rol,
                    estado,
                    etiquetas_json,
                ),
            )

        # Identidades para deduplicacion (DNI, Correo, Telefono)
        cur.execute("delete from candidate_identities where candidato_id=?", (cand_id,))
        for tipo_id, val in [("documento", doc_norm), ("correo", correo.lower()), ("telefono", tel_norm)]:
            cur.execute(
                "insert into candidate_identities (id, candidato_id, tipo, valor_normalizado, activa, version, creado_en, actualizado_en) values (?, ?, ?, ?, 1, 1, datetime('now'), datetime('now'))",
                (nuevo_id(), cand_id, tipo_id, val),
            )

        # Postulacion a la convocatoria correspondiente
        clave_idemp = f"postulacion-{cand_id}-{version_perfil_id}"
        post_existente = cur.execute(
            "select id from applications where clave_idempotencia=?",
            (clave_idemp,),
        ).fetchone()

        if not post_existente:
            cur.execute(
                "insert into applications (id, cliente_id, candidato_id, version_perfil_id, fuente, estado, clave_idempotencia, version, creado_en, actualizado_en) values (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))",
                (nuevo_id(), cliente_id, cand_id, version_perfil_id, fuente, "registrada", clave_idemp),
            )

        print(f" [{i+1:02d}/25] Candidato: {nombres} {apellidos} (DNI: {doc_norm}) -> Convocatoria: {conv_codigo} [{estado.upper()}]")

    con.commit()
    print("\n¡Sembrado completado con éxito!")


if __name__ == "__main__":
    main()
