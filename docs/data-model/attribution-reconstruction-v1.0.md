# Reconstrucción as-of de AttributionClaim — contrato v1.0

## Propósito

Este contrato vincula una atribución concreta con los snapshots exactos que respaldan sus observaciones. La reconstrucción no consulta proveedores ni resuelve identificadores contra estados actuales.

## Contrato y algoritmo

- Schema: `schemas/attribution-reconstruction-manifest-v1.0.schema.json`.
- Implementación: `iwfi/attribution_reconstruction.py`.
- Pruebas: `tests/test_attribution_reconstruction.py`.
- Canonicalización: `IWFI-JSON-C14N-1`.

La canonicalización v1 se define de forma cerrada: serialización JSON UTF-8, claves de objetos ordenadas, separadores compactos `(",", ":")`, `ensure_ascii=false` y `allow_nan=false`. El hash SHA-256 del claim se calcula sobre el objeto JSON exacto entregado al constructor. No se afirma que este formato sea RFC 8785/JCS; es un formato interno versionado de IWFI. Cualquier cambio exige nueva versión.

## Dependencias de evidencia

El constructor recoge referencias de:
- `observation_id`;
- `observation_ids`;
- `source_observation_ids`.

Se ha probado tanto con Entity Attribution Claim como con un Execution Participant Role Claim v1.1. Durante la verificación se vuelve a extraer el conjunto de observaciones del claim y se compara con la unión de las referencias del manifiesto; un manifiesto que omita o invente una observación falla incluso si alguien recalcula su hash local.

Cada identificador de observación debe mapearse explícitamente a uno o varios `source_snapshot_id`. Cada snapshot debe estar presente en el conjunto congelado y tener `retrieved_at_utc` no posterior al cutoff. Si falta una correspondencia o el snapshot es posterior al cutoff, la construcción falla.

Se conservan tanto observaciones que sustentan como las que contradicen la atribución. No se descartan contra-evidencias para producir una reconstrucción aparentemente concluyente.

## Tiempo bitemporal

- `claim_recorded_at_utc`: cuándo IWFI registró el claim.
- `knowledge_cutoff_utc`: límite de lo que podía conocerse para esta reconstrucción.
- `valid_time_utc`: instante del mundo/periodo sobre el que se evalúa el claim.
- `retrieved_at_utc`: cuándo IWFI obtuvo cada snapshot.

La función rechaza claims registrados después del cutoff, snapshots recuperados después del cutoff y valid_time fuera del intervalo de validez explícito del claim. Los límites null permanecen desconocidos; no se interpretan como prueba de vigencia ilimitada.

## Integridad offline

El verificador comprueba:
1. hash del manifiesto;
2. hash del claim y correspondencia de ID, versión y recorded_at;
3. cutoff y valid_time;
4. identidad exacta de cada snapshot;
5. disponibilidad del payload y SHA-256/tamaño.

Estados como `SNAPSHOT_MISSING`, `PAYLOAD_UNAVAILABLE`, `SNAPSHOT_REFERENCE_MISMATCH` y `SNAPSHOT_AFTER_CUTOFF` producen fallo. El verificador no utiliza red ni proveedores.

Un hash local prueba consistencia de bytes con el descriptor, no autoría, firma del proveedor, veracidad ni autorización legal. Si el payload no puede retenerse, el claim no puede declararse plenamente reconstruible a partir de ese payload: el resultado debe permanecer incompleto explícitamente.

## Persistencia append-only local

`iwfi/append_only_journal.py` añade un journal JSONL local de referencia con secuencia, hash del registro anterior, hash del registro actual, rechazo de IDs duplicados y `fsync` por append. `verify_journal` detecta alteración, reordenamiento, truncamiento y ruptura de la cadena.

Es una referencia local de un solo escritor, no almacenamiento WORM ni garantía contra un administrador privilegiado. Una reescritura total con recálculo de hashes requiere anclaje externo independiente o firma para ser detectada. La persistencia del journal no convierte por sí sola un claim en reconstruible: los payloads restringidos o no disponibles siguen siendo incompletos.

## Límites

Esta capa congela y verifica entradas de atribución. No vuelve a ejecutar todavía el motor semántico que deriva identidad, lado BUY/SELL o rol económico desde observaciones; tampoco demuestra causalidad. Siguen pendientes integración durable con los contratos Source Observation y Actor Registry, replay semántico determinista, firma/anclaje externo, control de concurrencia multi-proceso, matriz real de derechos por proveedor y almacenamiento WORM.

No habilita captura real, polling, backfill ni almacenamiento productivo. Fixtures sintéticos únicamente; coste externo 0 USD.
