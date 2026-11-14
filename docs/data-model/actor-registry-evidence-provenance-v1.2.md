# Proveniencia tipada de evidencia del Actor Registry v1.2

## Objetivo y compatibilidad

Actor Registry v1.2.0 introduce referencias tipadas a contratos existentes sin copiar sus payloads. Los contratos 1.0.0 y 1.1.0 permanecen sin cambios. La adopción es explícita: los consumidores deben solicitar v1.2.0 y no reinterpretar cadenas antiguas como referencias tipadas.

Cada referencia tiene exactamente:
- `ref_type`: `SOURCE_OBSERVATION` o `ATTRIBUTION_CLAIM`.
- `ref_id`: identificador canónico del registro upstream.

El schema versionado está en `schemas/actor-registry-v1.2.schema.json`. Los campos `evidence_refs` y `counter_evidence_refs` mantienen polaridades separadas.

## Resolución y snapshots

El resolver recibe snapshots explícitos, no accede a red ni a bases de datos:

```python
snapshots = {
    "SOURCE_OBSERVATION": {"status": "COMPLETE", "records": [...]},
    "ATTRIBUTION_CLAIM": {"status": "PARTIAL", "records": [...]},
}
```

- `COMPLETE`: la ausencia de un ID permite concluir que no está en ese snapshot.
- `PARTIAL`: la ausencia significa `NOT_FOUND_IN_PARTIAL_SNAPSHOT`; no demuestra inexistencia.
- Snapshot no cargado: `SNAPSHOT_NOT_LOADED`.
- IDs duplicados: `AMBIGUOUS_DUPLICATE_ID`.
- Referencia inválida, no elegible o no resuelta: resultado fail-closed `INVALID_INPUT` cuando `require_all=True`.

El consumidor debe suministrar snapshots/versiones coherentes y completos para el ámbito consultado. El resolver no inventa que un snapshot parcial es completo.

## Point-in-time

La consulta requiere `knowledge_cutoff_utc` y `valid_time_utc`:
- Source Observation utiliza `retrieved_at_utc` como momento en que IWFI la conoció/recuperó.
- AttributionClaim utiliza `known_at_utc` y `recorded_at_utc`; ambos deben estar dentro del cutoff.
- Para AttributionClaim, `valid_from_utc/valid_to_utc` debe cubrir el instante válido.
- Una observación recuperada después del cutoff no entra en la reconstrucción aunque su evento sea anterior.
- Una afirmación retroactiva descubierta después tampoco entra.

## Propagación epistemológica y ciclos

El resolver devuelve el `epistemic_status` original del AttributionClaim. Vincular un claim DISPUTED, INFERRED o PROVIDER_LABELLED nunca lo convierte en VERIFIED.

Para evitar ciclos, un AttributionClaim usado como evidencia solo puede referenciar Source Observations en su lista `evidence_refs`; no puede encadenar otro AttributionClaim ni volver a Actor Registry. La resolución es determinista y no realiza transitividad.

Supporting evidence y counter evidence se resuelven por separado. No se calcula un score neto ni se elimina una contradicción por orden de llegada.

## Límites semánticos

Una Source Observation de tipo transferencia/transacción on-chain no prueba por sí sola BUYER, SELLER, BENEFICIAL_OWNER, OWNS o CONTROLS. La función permite pasar `predicate` para rechazar esa utilización. La detección de una ejecución real y su lado requiere evidencia de ejecución adecuada según el contrato TradeExecution; una transferencia no se convierte en trade.

Una referencia externa/documental debe existir primero como Source Observation autorizada. Este cambio no autoriza nuevas fuentes ni modifica políticas de retención.

## Pruebas y alcance

`tests/test_typed_evidence_provenance.py` contiene casos sintéticos independientes BTC/ETH para referencias válidas, ausentes, duplicadas, tardías, disputadas, parciales, tipo incorrecto, ciclos y separación de contraevidencia.

No hay red, proveedores, credenciales, captura real, polling, backfill, persistencia productiva ni servicios pagos. Coste externo: 0 USD.
