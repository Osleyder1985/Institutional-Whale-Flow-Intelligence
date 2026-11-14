# Journal append-only local y cadena de integridad — referencia v1.0

## Alcance

`iwfi/append_only_journal.py` implementa un journal JSONL local de referencia:
- asigna secuencia monotónica;
- enlaza cada registro con el hash del registro anterior;
- calcula SHA-256 sobre el envelope canónico;
- rechaza reutilización de `event_id`;
- valida toda la cadena antes de aceptar un nuevo append;
- hace `flush` y `fsync` tras cada línea;
- detecta modificación, reordenamiento, duplicación, truncamiento y enlaces rotos.

No descarga ni consulta fuentes. Las pruebas usan únicamente directorios temporales y eventos sintéticos.

## Modelo de amenaza y límites

La cadena detecta alteraciones accidentales o modificaciones que no recalculen correctamente los hashes posteriores. **No impide que un operador privilegiado reescriba el archivo completo y regenere toda la cadena.** Para elevar la garantía se necesita anclaje independiente del hash de cabeza (por ejemplo, firma con clave protegida o publicación en un segundo dominio de confianza), controles de acceso y copias verificables.

La implementación asume un solo proceso escritor. No proporciona bloqueo interproceso, replicación, almacenamiento WORM, recuperación transaccional frente a todos los fallos del sistema de archivos ni protección contra compromiso del host. `fsync` solicita persistencia al sistema operativo, pero no equivale a certificación de durabilidad del hardware.

El journal es una referencia local gratuita, no almacenamiento productivo ni autorización para retener payloads. Deben registrarse solo eventos y metadatos cuya conservación esté permitida por la política aplicable.

## Formato de registro

Cada línea contiene:
- `canonicalization`: `IWFI-JSON-C14N-1`;
- `sequence`: entero consecutivo desde 1;
- `previous_record_hash`: SHA-256 del envelope anterior o hash génesis de 64 ceros;
- `event`: objeto JSON con `event_id` único;
- `record_hash`: SHA-256 del canonical JSON de canonicalization, sequence, previous hash y event.

La canonicalización es interna y versionada; no se afirma compatibilidad RFC 8785/JCS.

## Estados de verificación

Incluye `CHAIN_VERIFIED`, `HASH_MISMATCH`, `CHAIN_LINK_MISMATCH`, `SEQUENCE_MISMATCH`, `DUPLICATE_EVENT_ID`, `TRUNCATED_LINE` e incidencias de formato/IO. Una cadena válida demuestra consistencia interna desde el hash génesis, no autenticidad externa ni ausencia de reescritura privilegiada.

## Pendiente

- Anclaje externo firmado y rotación/gestión de claves.
- Control de concurrencia multi-proceso y recuperación crash-safe específica por plataforma.
- Integración de eventos con los contratos Source Observation y AttributionClaim existentes.
- Replay semántico del motor de atribución con versiones y parámetros congelados.
- Matriz de derechos/retención por proveedor.

Coste externo: 0 USD. Sin servicios pagos, APIs, credenciales ni captura real.
