# ADR-005 — Gmail API con OAuth y secretos cifrados editables en caliente

- **Estado:** Aceptada
- **Fecha:** 2026-09-09

## Contexto

El sistema debe enviar comunicaciones a los candidatos y permitir que el operador
configure sus propias credenciales —la API key del proveedor de IA y el par
cliente/secreto de Google OAuth— sin editar ficheros ni redesplegar.

Eso plantea dos preguntas que conviene resolver juntas, porque comparten el mismo
riesgo: dónde viven los secretos y quién puede usarlos.

## Decisión

**Envío exclusivamente por la API oficial de Gmail con OAuth 2.0.** No se usa
SMTP en ningún caso.

**Configuración en dos niveles.** La estática vive en el entorno y se lee al
arrancar: URL de base de datos, claves maestras de cifrado, límites de seguridad.
La editable en caliente vive en base de datos y se administra desde el panel:
proveedor, API key, modelo, credenciales de Google, feature flags.

**Todo valor marcado como secreto se cifra antes de tocar la base de datos**, con
Fernet y una clave derivada de `VERA_SECRET_KEY` mediante HKDF, usando el
propósito como material de derivación.

## Justificación

**Por qué no SMTP.** Requiere almacenar una contraseña reutilizable con permisos
amplios sobre la cuenta. OAuth permite un alcance mínimo —`gmail.send`, que no
concede lectura del buzón—, es revocable sin cambiar credenciales de la cuenta y
devuelve un identificador de mensaje que sirve como prueba de envío en la
auditoría.

**Por qué los secretos no están en `.env`.** El operador del laboratorio no
debería tener que editar ficheros para probar su clave. Y una clave en un fichero
del proyecto termina, tarde o temprano, en un commit.

**Por qué el cifrado ocurre en el `set` y no en el llamante.** Confiar en que
cada punto de escritura recuerde cifrar es una garantía que se rompe la primera
vez que alguien añade un campo. La responsabilidad vive en un único sitio.

**Por qué derivar por propósito.** Comprometer el material de un propósito no
compromete el resto. Hay un test que lo verifica: un secreto cifrado para un
propósito no se descifra con la clave de otro.

## Garantías que el diseño hace verificables

- **Ningún endpoint devuelve un secreto en claro.** La vista pública siempre
  enmascara, y acompaña el valor con un indicador `is_set` para que la interfaz
  pueda distinguir "no configurado" de "configurado pero oculto".
- **Dejar un campo de secreto en blanco conserva el valor guardado.** Permite
  reenviar el formulario del panel sin borrar la clave por descuido.
- **El logger redacta por patrón**, no por confianza en el llamante: claves de
  Google, tokens OAuth, JWT, correos y teléfonos se sustituyen en el formatter.
- **El agente no puede enviar.** Aunque las credenciales estén configuradas, VERA
  solo puede *preparar* un borrador desde una plantilla aprobada. El envío lo
  hace el backend tras comprobar que el destinatario coincide con el correo
  registrado del candidato, verificar la idempotencia y, en las categorías
  sensibles, exigir aprobación humana.
- **La idempotencia se garantiza en el motor**, con una restricción de unicidad
  sobre la clave. Cualquier comprobación en la aplicación puede perder una
  carrera entre dos procesos; una restricción de base de datos no.

## Consecuencias

**Positivas.** Un volcado accidental de la base de datos no expone credenciales.
La configuración se cambia sin desplegar. El alcance mínimo de OAuth limita el
daño si la credencial se compromete.

**Negativas.** Perder `VERA_SECRET_KEY` hace irrecuperables los secretos cifrados
y obliga a reintroducirlos. Es intencionado: la alternativa sería guardar la clave
junto a lo que protege.

El flujo OAuth de Gmail está diseñado pero no implementado: el panel recoge y
cifra las credenciales, y falta el intercambio de código por token y el envío
real. Queda registrado como pendiente en el README.

## Nota sobre cuentas personales

La cuenta indicada para el laboratorio es de tipo `@gmail.com`, no de Workspace.
La API funciona igual con OAuth, pero los límites de envío y el proceso de
verificación de la aplicación son distintos. Para un laboratorio es suficiente;
antes de producción hay que revisar ambos puntos.
