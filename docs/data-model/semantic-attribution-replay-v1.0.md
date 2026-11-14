# Replay semántico de atribución de participantes — contrato de referencia v1.0

## Propósito

`iwfi/semantic_attribution_replay.py` vuelve a ejecutar el resolver temporal existente de participantes de ejecuciones usando un conjunto explícito de entradas congeladas. A diferencia de verificar solo hashes de snapshots, esta capa sí vuelve a producir el resultado semántico del resolver.

## Entradas que quedan vinculadas

- registro de ejecuciones (incluye `event_time_utc`, `execution_id` y referencias de claims);
- registro de claims de roles de participantes;
- Actor Registry;
- lista exacta de `observation_ids`;
- `knowledge_cutoff_utc`.

Cada entrada recibe SHA-256 bajo `IWFI-JSON-C14N-1`. Se registra el identificador/versión del resolver, el tiempo válido, el cutoff, el resultado y su hash. El verificador vuelve a ejecutar el resolver y compara tanto hashes de entrada como salida.

## Semántica temporal y correcciones

El motor invocado es `resolve_execution_participants_as_of`, que separa el cutoff de conocimiento del tiempo del evento y aplica la elegibilidad temporal de actores y relaciones. Una corrección debe almacenarse como un nuevo snapshot de entrada/claim registry; no se modifica el snapshot histórico. El fixture de prueba demuestra:
- la versión histórica produce un BUYER DIRECT con actor identificado;
- una versión posterior del claim corrige el mismo rol a UNKNOWN;
- el replay histórico con sus entradas originales conserva exactamente el mismo hash de resultado;
- el replay actual refleja la corrección y produce otro hash.

Este ejemplo es sintético. No prueba por sí mismo el flujo de persistencia de snapshots a un backend productivo ni autoriza convertir transferencias en operaciones de mercado.

## Límites

- El replay cubre el resolver de roles de participantes de ejecuciones, no todos los módulos de IWFI ni la extracción de observaciones desde payloads originales.
- El identificador/versión del algoritmo es una constante declarada por este wrapper; cambios incompatibles en el resolver requieren actualizar esa versión y los fixtures.
- Los hashes prueban igualdad de las entradas suministradas, no autoría externa ni que el caller haya seleccionado el snapshot correcto.
- Los inputs deben provenir de snapshots preservados por la capa de provenance y de acuerdo con los derechos aplicables.
- El wrapper no consulta red, APIs, proveedores ni servicios externos.

Coste externo: 0 USD. Fixtures sintéticos BTC/ETH existentes; este caso semántico específico usa ETH.
