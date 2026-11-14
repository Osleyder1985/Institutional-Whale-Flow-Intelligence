# Reconstrucción integrada de Actor Registry v1.2 — referencia v1.0

## Propósito

`iwfi/verified_actor_registry_reconstruction.py` conecta la verificación offline de Attribution Reconstruction Manifest, los bytes de snapshots, Source Observation, AttributionClaim y el resolver de Actor Registry v1.2.

## Formato del payload JSON

Cada snapshot usado por esta capa debe contener bytes UTF-8 JSON con:
- `record_type`: `SOURCE_OBSERVATION` o `ATTRIBUTION_CLAIM`;
- `coverage_status`: `COMPLETE` o `PARTIAL`;
- `records`: array de objetos con `observation_id` o `claim_id` respectivamente.

Los bytes se verifican primero con `verify_snapshot_payload`. Solo después se decodifican los registros. La recuperación del descriptor se usa como fallback explícito para `retrieved_at_utc` cuando el registro no lo trae; no se infiere el tiempo del evento. Varias colecciones se consideran PARTIAL si cualquiera de sus snapshots es PARTIAL.

## Secuencia fail-closed

1. Verifica el hash del manifiesto, claim y dependencias.
2. Exige igualdad exacta entre cutoff/valid_time solicitados y los congelados en el manifiesto.
3. Comprueba que cada snapshot sea anterior o igual al cutoff.
4. Verifica SHA-256 y tamaño de los bytes exactos.
5. Valida media type, JSON, record_type, coverage_status e IDs.
6. Construye snapshots tipados únicamente con registros de bytes verificados.
7. Añade el AttributionClaim congelado al conjunto de claims para resolver referencias explícitas del Actor Registry v1.2.
8. Ejecuta `resolve_actor_registry_evidence_as_of` sin red ni acceso a proveedores.

## Estados y límites

- `ACTOR_REGISTRY_RECONSTRUCTED`: manifiesto, bytes y referencias tipadas pasaron la verificación/resolución.
- `INTEGRITY_FAILED`: hash, payload, dependencia o claim no coincide.
- `EVIDENCE_RESOLUTION_FAILED`: una referencia no se puede resolver de forma segura.
- `INVALID_INPUT`: contrato, cutoff o entrada inválida.

Este resultado no prueba que la atribución sea verdadera, que el actor sea beneficiario efectivo ni que un movimiento causara variación de precio. Conserva `epistemic_status` del claim sin elevarlo. Una transferencia on-chain no se convierte en ejecución ni propiedad.

Los payloads con `payload_retention` distinto de RETAINED se reportan en `snapshot_retention_warnings`: aunque bytes se hayan suministrado transitoriamente para esta ejecución, no se afirma que puedan reconstruirse en el futuro. El caller debe cumplir la política de derechos.

El manifiesto raíz debe enumerar los IDs de observación usados mediante los campos reconocidos por Attribution Reconstruction v1.0 (por ejemplo, `source_observation_ids` o `supporting_evidence[].observation_id`); cada uno debe mapearse al snapshot exacto. El módulo solo reconstruye referencias presentes en dependencias del manifiesto. El contrato de manifiesto v1.0 sigue recogiendo IDs de observaciones del claim; una ampliación futura deberá versionar el manifiesto para congelar dependencias directas del Actor Registry y todas las claim refs no incluidas en el claim raíz.

Fixtures sintéticos ETH; coste externo 0 USD. Sin red, captura real, polling, backfill, APIs ni servicios pagos.
