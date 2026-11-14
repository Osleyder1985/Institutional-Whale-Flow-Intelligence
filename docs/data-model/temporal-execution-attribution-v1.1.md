# Resolución temporal de participantes y Actor Registry v1.1

## Propósito

La identidad de un actor no puede validarse consultando solo si su `actor_id` existe en el registro actual. La resolución histórica debe separar dos ejes:

- `event_time_utc`: cuándo ocurrió la ejecución y cuándo debía ser válida la identidad/relación en el mundo real.
- `knowledge_cutoff_utc`: hasta cuándo IWFI puede utilizar información conocida y registrada.

Un claim con vigencia retroactiva pero descubierto o registrado después del cutoff no puede aparecer en una reconstrucción histórica de lo que IWFI sabía.

## Contrato

`schemas/actor-registry-v1.1.schema.json` introduce Actor Registry 1.1.0 sin alterar `actor-registry.schema.json` 1.0.0.

Cada alias, classification y relationship incorpora `recorded_at_utc` además de `known_at_utc`. Para ser visible, ambos timestamps deben ser <= `knowledge_cutoff_utc`, y el intervalo `valid_from_utc/valid_to_utc` debe cubrir el instante consultado.

Se exige `recorded_at_utc >= known_at_utc`. Los timestamps se expresan en UTC con segundos y sufijo Z.

## Resolución de identidad

`resolve_actor_identity_as_of` devuelve elegibilidad solo cuando:

1. Existe exactamente un actor con ese ID.
2. `known_at_utc` y `recorded_at_utc` no superan el cutoff.
3. El intervalo de vigencia cubre `valid_time_utc`.
4. `identity_status` no es UNKNOWN ni DISPUTED.

Una entidad disuelta puede ser elegible para una ejecución histórica si era conocida al cutoff y su vigencia cubría el evento. No se exige que siga activa en el presente.

Una identidad VERIFIED puede conservar un claim DIRECT. Si la identidad es INFERRED o PROVIDER_LABELLED, un claim de ejecución DIRECT se degrada a INFERRED. UNKNOWN/DISPUTED o actor no elegible producen abstención para ese participante, no selección de otro actor.

## Relaciones

`resolve_relationship_as_of` consulta únicamente aristas directas. Exige la doble temporalidad y devuelve DISPUTED cuando las afirmaciones elegibles se contradicen o incluyen una afirmación DISPUTED. No calcula transitividad ni convierte MANAGES, CUSTODIES_FOR, CONTROLS u OPERATES en beneficial ownership.

La relación solo debe utilizarse como evidencia para una atribución cuando el caso analítico declare explícitamente que depende de esa relación y conserve la referencia de evidencia. El ActorType/Classification no sustituye a participant_role.

## Integración con ejecuciones

`resolve_execution_participants_as_of` valida el claim registry y el enlace bidireccional TradeExecution v1.1, filtra claims posteriores al cutoff y exige que los actores nominados sean elegibles en el Actor Registry v1.1. Los participantes no elegibles quedan UNKNOWN; no se promueve el custodio, broker, gestor o fondo a beneficiario final por inferencia.

Esta versión no cambia el resolver legacy ni migra automáticamente contratos 1.0.0. La adopción debe ser explícita por los consumidores.

## Límites de la implementación

- Solo fixtures sintéticos BTC/ETH.
- No hay conectores, captura real, polling, backfill, persistencia productiva ni proveedores.
- Las relaciones temporales están disponibles como función independiente; no se presume que toda atribución de ejecución dependa de una relación corporativa.
- La integración no prueba que una entidad ejecutó una orden si la fuente solo acredita una transferencia, holding, ETF flow o clasificación institucional.
