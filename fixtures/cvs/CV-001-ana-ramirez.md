<!--
DOCUMENTO FICTICIO — laboratorio de VERA ATS.
Persona inventada. Cualquier parecido con alguien real es casual.

Propósito de esta pieza: candidatura fuerte para VAC-001. Debe superar todos los
filtros obligatorios y obtener una puntuación alta con evidencia verificable.
-->

# Ana Lucía Ramírez Ochoa

**Ingeniera de Software Backend**

Correo: ana.ramirez.ochoa@example.test
Teléfono: +00 000 000 000
Ubicación: Lima, Perú
LinkedIn: linkedin.com/in/ana-ramirez-ochoa-ficticia

---

## Perfil profesional

Ingeniera de software con 7 años de experiencia en desarrollo backend, centrada en
servicios distribuidos de alta disponibilidad. Trabajo habitualmente con Python y
PostgreSQL en entornos de microservicios desplegados en contenedores. En los
últimos tres años he asumido decisiones de arquitectura y acompañamiento técnico
de personas con menos experiencia.

---

## Experiencia profesional

### Senior Backend Engineer en Fintech Andina S.A.C. (2021 — actualidad)

Plataforma de pagos con un volumen aproximado de 400.000 transacciones diarias.

- Diseñé y desarrollé 9 microservicios en **Python** con **FastAPI**, sustituyendo
  progresivamente un monolito heredado en PHP.
- Modelé el esquema transaccional en **PostgreSQL** e introduje particionado por
  rango de fechas, reduciendo el tiempo de las consultas de conciliación de 14
  segundos a menos de 900 milisegundos.
- Implementé el sistema de idempotencia de la pasarela de pagos, que eliminó los
  cobros duplicados reportados por soporte.
- Introduje **Redis** como capa de caché y como backend de colas para el
  procesamiento asíncrono de notificaciones.
- Construí los pipelines de **CI/CD** con **GitHub Actions**, incluyendo ejecución
  de pruebas, análisis estático y despliegue automatizado sobre **AWS ECS**.
- Definí el estándar de observabilidad del equipo con **Prometheus** y **Grafana**,
  incorporando trazas distribuidas y `trace_id` propagado extremo a extremo.
- Acompaño técnicamente a tres personas del equipo mediante revisiones de código y
  sesiones de diseño semanales.

Tecnologías: Python, FastAPI, PostgreSQL, Redis, Docker, AWS, GitHub Actions,
Prometheus, Grafana, pytest.

### Backend Developer en Retail Digital Perú (2019 — 2021)

Plataforma de comercio electrónico con catálogo de aproximadamente 80.000 productos.

- Desarrollé APIs REST en **Python** con **Django REST Framework** para los
  módulos de catálogo, inventario y pedidos.
- Migré el motor de búsqueda interno a **Elasticsearch**, lo que redujo el tiempo
  medio de búsqueda de 2,1 a 0,4 segundos.
- Contenericé la aplicación con **Docker** y colaboré en su despliegue.
- Elevé la cobertura de pruebas del módulo de pedidos del 34 % al 81 %.

Tecnologías: Python, Django, PostgreSQL, Elasticsearch, Docker, Celery.

### Desarrolladora Junior en Consultora Sistemas del Sur (2018 — 2019)

- Mantenimiento de aplicaciones internas en Python y Java.
- Automatización de informes contables que ahorró unas 12 horas mensuales de
  trabajo manual al área financiera.

---

## Formación académica

**Ingeniería de Sistemas** — Universidad Nacional de Ingeniería, Lima.
Graduación: 2018.

**Especialización en Arquitectura de Software** — Programa de extensión
universitaria, 2022. 120 horas.

---

## Certificaciones

- AWS Certified Solutions Architect – Associate (2023)
- Certificación en Bases de Datos PostgreSQL Avanzado (2021)

---

## Idiomas

- Español: nativo
- Inglés: C1 (certificado, 2022)
- Portugués: B1

---

## Proyectos destacados

**Sistema de conciliación bancaria automatizada** (2023)
Servicio en Python y FastAPI que concilia diariamente unos 400.000 movimientos
contra los extractos de cinco entidades bancarias. Redujo el trabajo manual del
equipo de finanzas de 6 horas diarias a 20 minutos de revisión de excepciones.

**Migración de monolito a microservicios** (2021 — 2023)
Participé en el diseño y la ejecución de la descomposición del monolito de pagos.
El proyecto se completó sin interrupciones de servicio, aplicando despliegue
progresivo y patrón de estrangulamiento.

---

## Disponibilidad

Incorporación inmediata. Disponible para modalidad híbrida en Lima.
