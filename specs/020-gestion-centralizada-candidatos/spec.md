---
id: SPEC-020
titulo: Gestión centralizada y editable de candidatos
estado: VERIFICADO
responsable_producto: Usuario
creado: 2026-09-11
actualizado: 2026-09-11
---

# SPEC-020 — Gestión centralizada y editable de candidatos

## Problema y resultado esperado

La ficha general y sus contratos ya existen, pero la pantalla separa consulta,
alta y edición en pestañas y muestra una tabla parcial. Para el trabajo diario
esto obliga a buscar la persona en más de un lugar y mantiene la percepción de
que Excel es necesario para administrar la base completa.

TalentIA debe ofrecer una única vista operativa con la tabla general de personas
como punto de entrada. Desde la fila seleccionada se podrá abrir y editar la
ficha completa, además de registrar una persona nueva. SQLite, a través de
FastAPI, será la única fuente de verdad; CSV/XLSX quedará como entrada o salida
opcional y nunca como almacenamiento operativo.

## Usuarios

- **Recruiter:** buscar, filtrar, registrar y actualizar fichas desde una sola pantalla.
- **HR Manager:** consultar la base completa y corregir datos con trazabilidad.
- **Auditor:** confirmar que las escrituras respetan permisos, versión y auditoría.

## Alcance incluido

1. Tabla general de candidatos obtenida exclusivamente desde FastAPI.
2. Columnas generales, de contacto, laborales y de seguimiento disponibles según RBAC.
3. Búsqueda por nombre, cliente, reclutador, fuente, solicitud y postulación.
4. Filtros simples por reclutador y fuente.
5. Selección de una fila para editar la ficha completa con bloqueo optimista.
6. Alta de candidatos desde la misma pantalla mediante formulario enfocado.
7. Exportación CSV opcional de la vista filtrada, neutralizada contra fórmulas.
8. Conservación del flujo de importación histórica CSV/XLSX como función secundaria.
9. Estados de postulaciones visibles por vacante y no editables desde la ficha general.

## Fuera de alcance

- Edición masiva o borrado de candidatos.
- Cambios automáticos de pipeline, contratación, descarte, contacto o recomendación.
- Usar pandas, Excel o CSV como persistencia principal.
- Importar CV binarios desde hojas de cálculo.
- Cambiar la migración o el esquema SQLite existente.

## Requisitos funcionales

- **FR-020-001:** La primera sección de la pantalla debe ser la tabla general y mostrar
  todas las personas disponibles para el rol actual.
- **FR-020-002:** La tabla debe permitir búsqueda, filtros y selección de una única fila.
- **FR-020-003:** La selección debe abrir la ficha editable de esa persona sin exigir
  navegar a otra página o buscarla nuevamente.
- **FR-020-004:** El guardado debe enviar `expected_version` y mostrar conflictos sin
  sobrescribir cambios más recientes.
- **FR-020-005:** El alta y la edición deben cubrir los campos aprobados en SPEC-018.
- **FR-020-006:** La edad calculada debe ser de solo lectura cuando existe fecha de nacimiento.
- **FR-020-007:** Los estados de selección deben mostrarse por postulación y vacante;
  no se modificarán desde la ficha general.
- **FR-020-008:** La exportación CSV debe reflejar la vista filtrada, neutralizar fórmulas
  y respetar los datos ya minimizados por la API.
- **FR-020-009:** La pantalla debe explicar que importar y exportar son acciones opcionales.

## Requisitos no funcionales

- **NFR-020-001:** Streamlit no accederá directamente a SQLite ni al dominio.
- **NFR-020-002:** La lógica de filas, filtros y CSV será pura y tendrá pruebas sin red.
- **NFR-020-003:** La interfaz priorizará pocas acciones visibles y lenguaje no técnico.
- **NFR-020-004:** La tabla usará componentes nativos de Streamlit y será utilizable en
  escritorio y móvil mediante desplazamiento o apilado responsivo.
- **NFR-020-005:** La regresión completa deberá permanecer aprobada.

## Seguridad, privacidad y gobierno

- **SEC-020-001:** La lectura y escritura conservarán `candidate:read`,
  `candidate:write` y `candidate:pii:read` como límites efectivos.
- **SEC-020-002:** Las columnas sensibles no se incorporarán al DataFrame del navegador
  si el rol no tiene permiso para recibirlas.
- **SEC-020-003:** La exportación nunca incluirá datos diferentes a los entregados por la API.
- **SEC-020-004:** Cada actualización seguirá auditada por el backend.
- **SEC-020-005:** La interfaz no inferirá aptitud ni alterará decisiones de selección.

## Fuente de verdad y rollback

`talentia.db`, accedida mediante los contratos FastAPI existentes, continúa como
fuente de verdad. El rollback consiste en restaurar la vista anterior y retirar
los helpers de presentación; no requiere migración ni modificación de datos.

## Decisión de aprobación

La solicitud explícita del usuario del 11 de septiembre de 2026 aprueba esta
especificación y autoriza su implementación, pruebas y documentación local.
