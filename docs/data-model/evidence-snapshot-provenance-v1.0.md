# Evidencia inmutable y reconstrucción offline — contrato v1.0

## Alcance

Esta implementación establece integridad de snapshots y un journal local de referencia sin red ni servicios externos. No descarga, captura ni publica datos de proveedores. Los fixtures son sintéticos y el coste externo es 0 USD.

Archivos:
- `schemas/evidence-snapshot-v1.0.schema.json`: contrato JSON Schema Draft 2020-12.
- `iwfi/evidence_snapshot_provenance.py`: descriptor, hashing SHA-256, verificación offline, relaciones de revisión, manifiesto determinista y ledger append-only en memoria.
- `iwfi/append_only_journal.py`: journal JSONL local con secuencia y hash chain.
- `tests/fixtures/evidence-snapshots-v1.0.json`: fixtures sintéticos BTC/ETH.
- `tests/test_evidence_snapshot_provenance.py` y `tests/test_append_only_journal.py`: pruebas de integridad y regresión.

## Separación de tiempos

- `published_at_utc`: publicación declarada por la fuente; puede ser null.
- `retrieved_at_utc`: momento en que IWFI recuperó el artefacto.
- `recorded_at_utc`: momento en que IWFI registró el descriptor.
- El tiempo del evento debe permanecer en el contrato de observación/claim que describe el evento; no se sustituye por la fecha de recuperación.

Todos los timestamps presentes en este contrato usan UTC estricto `YYYY-MM-DDTHH:MM:SSZ`. Un valor desconocido se mantiene null; no se infiere.

## Hash y canonicalización

- `RAW_BYTES` calcula SHA-256 sobre los bytes exactos entregados a la función.
- `CANONICAL_JSON` exige una `canonicalization_version` explícita. El descriptor de snapshot no implementa por sí solo un canonicalizador de payload; el llamador debe entregar bytes canónicos ya producidos por una implementación versionada.
- El journal utiliza `IWFI-JSON-C14N-1` para sus envelopes JSON, con claves ordenadas, separadores compactos, UTF-8, `ensure_ascii=false` y `allow_nan=false`.
- No se afirma compatibilidad RFC 8785/JCS.
- Un hash no prueba autoría, autenticidad del proveedor, veracidad ni permiso legal de conservación.

## Derechos y retención

Decisiones soportadas:
- `RETAINED`: solo si se entregan bytes exactos, referencia de almacenamiento y permiso explícito para retener y calcular hash.
- `NOT_RETAINED_POLICY`: no se registra referencia de almacenamiento; puede existir hash solo si la política permite calcularlo.
- `NOT_RETAINED_UNAVAILABLE`: el artefacto no está disponible para retención.

La función falla de forma cerrada cuando se solicita retener sin permiso de hash. La matriz de derechos real por proveedor aún debe ser suministrada y evaluada antes de cualquier captura. Este contrato no autoriza conservar payloads.

## Append-only y relaciones

Cada recuperación debe recibir un `source_snapshot_id` nuevo. `AppendOnlySnapshotLedger` es un modelo de referencia en memoria que rechaza IDs reutilizados y expone registros de solo lectura.

El journal local añade eventos sin reemplazar líneas previas, encadena hashes y ejecuta `fsync` después de cada append. Se asume un solo proceso escritor. Detecta alteraciones sin recálculo, reordenamiento, truncamiento, duplicados y ruptura de enlaces. No es WORM: un administrador privilegiado puede reescribir el archivo completo y recalcular la cadena. Para detectar ese escenario se requiere anclaje independiente o firma con clave protegida.

Las relaciones son registros nuevos con `from_snapshot_id`, `to_snapshot_id` y uno de:
`SUPERSEDES`, `CORRECTS`, `CONTRADICTS`, `RETRACTS`, `REVOKES_ACCESS`.
No se sobrescribe la versión anterior. El estado de derechos/retención no debe confundirse con validez factual o estado editorial.

## Manifiesto de reconstrucción

El manifiesto congela:
- ID del AttributionClaim;
- versiones de contratos;
- identificador y versión del algoritmo;
- parámetros explícitos;
- cutoff de conocimiento y tiempo válido;
- IDs y hashes de todos los snapshots de dependencia.

Su hash se calcula sobre JSON UTF-8 determinista con claves ordenadas y separadores compactos. La verificación offline comprueba el hash del manifiesto, la identidad exacta de cada snapshot y el SHA-256/tamaño de cada payload disponible. Si falta un snapshot o payload, la reconstrucción no se declara válida.

## Límites y siguientes pasos pendientes

Esta entrega todavía no implementa:
1. anclaje externo firmado del hash de cabeza;
2. control de concurrencia multi-proceso ni garantías WORM;
3. integración completa del manifiesto y journal con Source Observation, AttributionClaim y Actor Registry v1.2;
4. reconstrucción semántica completa del resultado de AttributionClaim;
5. matriz de permisos por proveedor ni políticas de borrado/retención legal;
6. verificación criptográfica externa del origen o firma del proveedor.

Por tanto, el estado es **integridad offline de snapshots, manifiesto y journal local de referencia**, no reconstrucción integral de todas las atribuciones históricas. No se habilita captura real, polling, backfill ni persistencia productiva.
