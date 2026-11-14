# Checkpoints firmados Ed25519 para el journal IWFI v1.0

## Objetivo

El hash chain local detecta modificaciones sin recálculo, pero un administrador privilegiado puede reescribir el archivo completo y recalcularlo. Este módulo añade checkpoints firmados Ed25519 para que un verificador externo pueda detectar que un journal presentado no coincide con un checkpoint previamente recibido.

## Modelo

Un checkpoint firma, bajo canonicalización `IWFI-JSON-C14N-1`:
- `journal_id`;
- secuencia y hash de cabeza del journal;
- hash del checkpoint anterior;
- hora declarada de emisión;
- algoritmo Ed25519 y fingerprint SHA-256 de la clave pública.

El verificador exige una clave pública de confianza suministrada fuera del propio checkpoint. Nunca confía en una clave pública incluida por el documento que se verifica. La cadena de checkpoints exige journal_id constante, secuencia creciente y continuidad exacta del hash del checkpoint anterior.

## Operación y anclaje independiente

1. Mantener la clave privada fuera del repositorio y, preferiblemente, fuera del equipo que almacena el journal.
2. Crear un checkpoint solo después de que el journal pase su verificación.
3. Copiar el checkpoint firmado a un segundo dominio de confianza bajo control independiente (por ejemplo, medio offline separado o repositorio externo con control distinto).
4. Conservar la clave pública/fingerprint por un canal de confianza independiente.
5. Verificar posteriormente firma, continuidad de checkpoints y coincidencia del hash de cabeza con el prefijo del journal.

El código ofrece generación de claves para fixtures/pruebas. No escribe claves privadas al disco ni implementa un gestor de secretos. El usuario/operador debe protegerlas y respaldarlas de forma segura.

## Límites de seguridad

- Ed25519 demuestra que la clave privada correspondiente firmó el contenido; no demuestra que el evento sea verdadero ni que la hora declarada sea una trusted timestamp.
- Si la clave privada y el journal se comprometen juntos, el atacante puede firmar una historia reescrita. La separación física/administrativa de la clave y el anclaje independiente son controles operativos esenciales.
- Un checkpoint guardado solo junto al journal no es anclaje independiente.
- No es almacenamiento WORM, no impide borrado y no sustituye backups, control de acceso, auditoría ni política de retención.
- La rotación/revocación de claves y timestamping confiable quedan fuera de esta versión.
- El checkpoint solo fija una cabeza de journal; el payload original puede estar sujeto a eliminación legal/técnica. No debe interpretarse como autorización de retención.

## Coste y alcance

Se usa la biblioteca libre y open source `cryptography`, fijada en `requirements-test.txt`. No hay servicios pagos, API, red, captura real, polling ni backfill. Claves y eventos de pruebas son sintéticos; coste externo: 0 USD.
