# Auditoría integral de objetivos, Issues y Pull Requests de IWFI

**Fecha de corte:** 2026-11-14  
**Repositorio:** `Osleyder1985/Institutional-Whale-Flow-Intelligence`  
**Rama auditada para la línea base:** `main`  
**Alcance:** inventario de todos los Issues abiertos y Pull Requests abiertas/no fusionadas visibles en GitHub en la fecha de corte. Esta auditoría no sustituye una revisión línea por línea de cada diff ni una verificación jurídica de proveedores.

## 1. Dictamen ejecutivo

IWFI tiene una base técnica considerable de contratos, validadores, trazabilidad y pruebas sintéticas. Sin embargo, el repositorio todavía no demuestra que funcione como una plataforma predictiva operativa con datos reales.

El principal problema organizativo no es la falta de trabajo técnico: es la falta de una jerarquía única y actualizada que conecte el objetivo de producto con los subsistemas, los datos autorizados, las pruebas científicas y la entrega de valor.

### Inventario a la fecha de corte

| Elemento | Cantidad | Estado |
|---|---:|---|
| Issues abiertas | 43 | Varias son requisitos válidos; otras parecen completadas o necesitan reestructuración |
| Pull Requests abiertas/no fusionadas | 28 | Incluyen cadenas apiladas, propuestas Draft y cambios con CI pendiente |
| Objetivo predictivo oficial | 1 | Definido en Issue #23; su documentación/actualización principal sigue en PR #24 |
| Fuentes aprobadas para captura productiva | 0 | Ninguna fuente ha superado todos los gates documentales y operativos |
| Muestras reales BTC+ETH integradas y verificadas | 0 pares completos | Las pruebas sintéticas no demuestran cobertura ni exactitud de datos reales |

Las cantidades anteriores son un recuento de GitHub, no una medida de avance porcentual.

## 2. Objetivo oficial que debe gobernar el repositorio

La decisión de producto registrada en Issue #23 el 2026-11-13 prevalece sobre descripciones anteriores de IWFI.

**IWFI debe ser una plataforma de inteligencia predictiva del precio de criptoactivos**, comenzando por BTC y ETH. Debe anticipar movimientos futuros y explicar las predicciones mediante evidencia, incertidumbre y validación temporal. No debe limitarse a mostrar transferencias o movimientos de ballenas.

Cada evaluación solicitada por el usuario debe poder producir, cuando los datos y la calibración lo permitan:

1. Dirección prevista: alcista, bajista, lateral o indeterminada.
2. Magnitud/rendimiento esperado e intervalos plausibles.
3. Precios objetivo y rangos de precios.
4. Zonas de soporte, resistencia, reacción y recorrido, con método y evidencia.
5. Tiempo estimado o distribución del tiempo hasta cada objetivo/zona.
6. Incertidumbre, calibración, calidad, cobertura y retrasos de datos.
7. Evidencia favorable, contraevidencia, hipótesis alternativas y condiciones de invalidación.
8. Resultado posterior observado, sin modificar la predicción original.
9. Comparación reproducible entre modelos y baselines.

Las probabilidades, umbrales, tiempos y magnitudes solo se publican si existe una base estadística suficiente y una calibración verificable. En caso contrario se informa `NOT_CALIBRATED`, `NOT_QUANTIFIED`, `NOT_ESTIMABLE` o abstención, según el contrato aplicable.

### Jerarquía funcional propuesta

- **P0 — Producto predictivo:** requisitos, Forecast/ForecastOutcome, targets/horizontes, datasets point-in-time, prevención de leakage y protocolo experimental.
- **P0 — Evidencia y datos:** fuentes autorizadas, observaciones canónicas, calidad, provenance, integridad temporal/canonicalidad y retención.
- **P1 — Inteligencia de mercado:** spot/microestructura, derivados, on-chain, actores, ejecuciones, posiciones, holdings, noticias, estructura técnica, sentimiento y relaciones cross-market.
- **P1 — Inteligencia de actores:** identificar qué se observó, quién puede atribuirse con evidencia, qué rol tuvo y qué permanece desconocido.
- **P1 — Plataforma:** persistencia, sincronización offline-first, seguridad, recuperación, auditoría y ciclo de vida de dispositivos.
- **P2 — Investigación predictiva:** backtesting temporal, walk-forward, holdout, baselines, ablations, costes, estabilidad por régimen y seguimiento de outcomes.
- **P2 — Entrega al usuario:** interfaz, informes, alertas configurables y exportación. Alertas, captura recurrente y análisis automático siguen desactivados salvo autorización explícita.

La inteligencia institucional y de ballenas es una familia importante de inputs y contexto; no debe reemplazar el objetivo predictivo ni recibir valor predictivo por presunción.

## 3. Estado real del producto y brechas

### 3.1 Documentación y coherencia del producto

- El `README.md` de `main` contiene únicamente el encabezado del proyecto. La actualización del README y la declaración del objetivo predictivo aparecen en PR #24, que continúa abierta.
- `docs/architecture/target-architecture.md` se declara explícitamente como propuesta y todavía describe el diseño provider-independent anterior. No equivale a una arquitectura productiva.
- `docs/roadmap/implementation-roadmap.md` conserva una formulación anterior: la primera pregunta del producto es quién actúa y qué hizo. Eso contradice la prioridad predictiva confirmada en #23.
- PR #39 propone el catálogo maestro de señales y fuentes y actualiza el registro de requisitos, pero sigue abierta.
- No hay una página de inicio que separe claramente capacidades integradas, propuestas, bloqueadas por permisos y pendientes de datos reales.

**Conclusión:** la documentación principal no representa todavía una única versión coherente del producto.

### 3.2 Fuentes y muestras reales

Issue #3 sigue abierta. La diligencia documental no equivale a aprobación de una fuente.

- Binance Vision histórico es candidato para investigación personal/no productiva, sujeto a los términos aplicables, retención y controles locales.
- Blockstream Esplora permanece como candidato restringido a prototipo/uso ligero; no se presume cuota gratuita recurrente ni permiso de escaneo masivo.
- PublicNode es candidato para una muestra Ethereum acotada, no una fuente aprobada ni una garantía de continuidad.
- Los proveedores comerciales revisados no han demostrado una API recurrente gratuita que satisfaga todos los requisitos de IWFI.
- Las operaciones públicas de un exchange pueden demostrar una ejecución en el venue, pero no identifican automáticamente al cliente ni al beneficiario efectivo.
- No se ha integrado un par de muestras reales reproducibles BTC y ETH que valide la cadena completa.

PR #116 es una evaluación documental y mantiene los candidatos como `NOT_APPROVED`. PR #110 declara que no existe todavía una transacción real mainnet integrada; PR #112 declara que sus snapshots de exposición son sintéticos.

**Conclusión:** no hay base para declarar validada la cobertura real del sistema, ni para entrenar o evaluar modelos con resultados de mercado fiables.

### 3.3 Capacidades que sí tienen base implementada

La línea base y la hoja de ruta registran contratos integrados para Source Observation, Attribution Claims, Movement Ledger, resolución de observaciones, Actor Registry y Trade Execution. También se han integrado controles de integridad de cadena y canonicalidad BTC/ETH mediante PR #117, que resolvió Issue #18.

PR #106 integró un procesador offline de Binance Spot aggTrades para métricas de microestructura, con validación de archivo y pruebas CI. Esto es una capacidad funcional de procesamiento local, pero no prueba que se hayan validado muestras reales BTC/ETH ni que exista una fuente live aprobada.

Las capacidades de flujos por dirección, agregación por entidad, contabilidad UTXO y exposición histórica aparecen en PR #107, #108, #110 y #112, que continúan sin fusionar. Sus propias descripciones delimitan que las pruebas son sintéticas y que faltan muestras reales.

### 3.4 Persistencia y operación multi-dispositivo

- Issue #16 / PR #17: ADR de persistencia, todavía Draft. No hay backend, base de datos física ni infraestructura seleccionada.
- Issue #22 / PR #118: contratos y simulación in-memory offline-first, con 355/355 pruebas Linux y 355/355 Windows en el HEAD reportado. No demuestra transporte real, inbox/outbox durable, concurrencia real, cifrado, restauración de servidor ni integración de clientes desktop/Android/iOS.
- Issue #71: el diseño de retención event-based fue aceptado por el propietario, pero el estado operativo sigue `NOT_ACTIVE`. Persisten gates de términos, ubicación local, sincronización/backup, capacidad y verificación de eliminación.

**Conclusión:** no debe iniciarse backend productivo ni declararse sincronización real completada hasta cerrar los gates correspondientes.

## 4. Inventario y clasificación de Issues abiertas

La clasificación siguiente identifica la función de cada Issue y la decisión organizativa recomendada. “Candidata a cierre” significa que existe evidencia de implementación relacionada, pero antes hay que comprobar cada criterio de aceptación y el estado integrado en `main`.

### A. Gobierno, fuentes, evidencia y plataforma

| Issue | Alcance | Evaluación / disposición recomendada |
|---:|---|---|
| #1 | Auditoría inicial y línea base | Parcial. Actualizar su línea base con esta auditoría y cerrar solo cuando README, roadmap, requisitos y gates estén coherentes. |
| #3 | Proveedores y primera fuente BTC/ETH | Crítica y genuinamente abierta. Mantener como gate de fuentes, muestras, coste y derechos. |
| #4 | Protección de `main` | Parcial. Ruleset activo según evidencia registrada; falta verificación de protección clásica/inherited con permisos suficientes. No hacer pruebas destructivas. |
| #6 | Contrato Source Observation | Candidata a cierre: PR #7 figura integrada en la hoja de ruta. Verificar criterios y artefactos en `main` antes de cerrar. |
| #8 | Attribution Claims temporal | Candidata a cierre: PR #9 figura integrada. Revisar criterios ampliados y evidencia actual antes de cerrar. |
| #16 | Persistencia auditable | Abierta correctamente. Depende de sincronización, retención, seguridad y parámetros operativos medidos. |
| #22 | Offline-first multi-dispositivo | Abierta correctamente. PR #118 cubre contratos/simulación, no integración durable. |
| #71 | Retención local y eliminación | Abierta correctamente. Diseño aceptado no significa activación operativa. |

### B. Objetivo predictivo, targets y datos de entrenamiento

| Issue | Alcance | Evaluación / disposición recomendada |
|---:|---|---|
| #23 | Objetivo predictivo y requisitos Forecast | Requisito rector. PR #24 lo documenta, pero no está fusionada. |
| #25 | Forecast y ForecastOutcome schemas | PR #26 abierta y apilada sobre #24. |
| #27 | Targets, horizontes, zonas y tiempo | PR #28 abierta y apilada sobre #26. |
| #29 | FeatureSnapshot y datasets point-in-time | PR #30 abierta y apilada sobre #28. |
| #36 | Protocolo experimental y valor incremental | Requisito científico transversal; no debe quedar subordinado a una sola familia de señales. |

### C. Familias de señales predictivas

| Issue | Familia | Evaluación / disposición recomendada |
|---:|---|---|
| #31 | Spot y microestructura | Especificación pendiente; reutilizar el procesador local existente donde corresponda. |
| #32 | Derivados, apalancamiento y liquidaciones | Especificación pendiente; separar venues, instrumentos y metodología. |
| #33 | On-chain, flujos institucionales y ballenas | Especificación pendiente; conservar la separación entre transferencia, trade, holdings y flujo agregado. |
| #34 | Noticias, eventos, regulación y macroeconomía | Especificación pendiente; incorporar disponibilidad temporal, rumores, filtraciones y correcciones. |
| #35 | Estructura técnica, volatilidad y regímenes | Especificación pendiente; toda feature debe ser calculable point-in-time. |
| #37 | Sentimiento social, atención y posicionamiento | Especificación pendiente; incluir sesgos, bots, manipulación y derechos de datos. |
| #40 | Relaciones cross-market, liquidez y stablecoins | Especificación pendiente; no equiparar supply de stablecoins con liquidez compradora. |
| #38 | Catálogo maestro de señales/fuentes/herramientas | PR #39 contiene el entregable; candidata a cierre tras CI, revisión y merge. |

### D. Actores, operaciones, posiciones y actividad

| Issue | Alcance | Evaluación / disposición recomendada |
|---:|---|---|
| #41 | Taxonomía y Actor Registry | Base implementada en contratos anteriores; revisar criterios y separar extensiones temporales/provenance antes de decidir cierre. |
| #42 | Descubrimiento y clustering de direcciones | Especificación pendiente; no inferir propiedad/control por heurística o etiquetas coincidentes. |
| #43 | Compras/ventas realmente ejecutadas y atribución | Parcial. La versión inicial de TradeExecution no cubre todos los roles; #77–#81 amplían multirol y evidencia. |
| #44 | Posiciones y holdings institucionales | Especificación pendiente; disclosures no equivalen automáticamente a trades. |
| #45 | Balances, acumulación/distribución y exposición de ballenas | Parcial. #107/#108 cubren flujos; #109/#110 cubren semántica UTXO; #111/#112 cubren exposición. Faltan datos reales y cobertura completa. |
| #46 | Exchanges, market makers, custodios y OTC | Especificación pendiente; distinguir inventario propio y flujos de clientes. |
| #47 | Eventos canónicos de actividad de actores | Especificación pendiente; debe consumir hechos y mantener inferencias etiquetadas. |
| #48 | Alertas configurables | Especificación pendiente; no activar alertas ni monitorización autónoma por defecto. |
| #49 | Impacto de actividad de actores sobre precio | Investigación pendiente; depende de #29 y #36, y debe distinguir asociación, valor predictivo y causalidad. |

### E. Atribución multirol y procedencia documental

| Issue | Alcance | Evaluación / disposición recomendada |
|---:|---|---|
| #77 | Claims multirol por ejecución | PR #78 implementa v1.1; abierta hasta revisión/merge y cierre de dependencias. |
| #79 | Actor Registry temporal en resolución multirol | PR #80 implementa v1.1; abierta y apilada sobre #78. |
| #81 | Referencias de evidencia contra Source Observation/AttributionClaim | PR #82 abierta; no declarar validada sin CI sobre HEAD actual. |
| #83 | Snapshots inmutables y reconstrucción de atribuciones | PR #84 abierta, dependiente de #82. |
| #85 | Autorización de retención por artefacto y paquetes locales | PR #86 abierta, dependiente de #84. |
| #88 | Intake documental y 20 ámbitos exactos | PR #89 abierta, dependiente de la cadena de políticas. |
| #90 | Adquisición local y sellado SHA-256 | PR #91 abierta, dependiente de PR #89 y cadena anterior. |
| #92 | Extracción local e informes de evidencia | PR #93 abierta, dependiente de #91. |
| #94 | Versionado de fuentes normativas | PR #95 abierta, dependiente de #93. |
| #96 | Conclusiones normativas ligadas a snapshots | PR #99 abierta, apilada sobre #95. |
| #97 | Afirmaciones documentales ligadas a snapshots | PR #98 abierta, apilada sobre #95. |

### F. Contabilidad UTXO y exposición histórica

| Issue | Alcance | Evaluación / disposición recomendada |
|---:|---|---|
| #109 | Modelo UTXO inputs/outputs antes de atribución BTC | PR #110 implementa una primera contabilidad sintética. Sigue abierta por muestra real y reconciliación mainnet. |
| #111 | Exposición histórica de direcciones controladas | PR #112 implementa contratos y agregación con gates de completitud. Sigue abierta por snapshots reales y validación de fuentes. |

## 5. Inventario de Pull Requests abiertas/no fusionadas

Las 28 PR abiertas se agrupan por finalidad y dependencia. La apertura de una PR no demuestra que esté lista para integrar. Antes de merge hay que volver a comprobar HEAD, base, CI, conflictos, conversaciones y compatibilidad con `main`.

### A. Producto predictivo y catálogo

| PR | Entrega | Relación | Disposición |
|---:|---|---|---|
| #24 | Objetivo predictivo oficial, README y arquitectura | #23 | Prioridad alta; revisar como primera PR de la cadena predictiva. |
| #26 | Forecast/ForecastOutcome v1 | #25; apilada sobre #24 | Integrar después de #24. |
| #28 | Targets y censura temporal v1 | #27; apilada sobre #26 | Integrar después de #26. |
| #30 | FeatureSnapshot/DatasetSnapshot point-in-time | #29; apilada sobre #28 | Integrar después de #28. |
| #39 | Catálogo maestro de señales y cobertura | #38; identifica brecha #40 | Revisar y fusionar como referencia del catálogo cuando CI y diff estén confirmados. |

### B. Persistencia y sincronización

| PR | Entrega | Relación | Disposición |
|---:|---|---|---|
| #17 | ADR de persistencia | #16; depende de #22 y #71 | Draft. Mantener sin backend ni selección física hasta cerrar dependencias y parámetros medidos. |
| #118 | Protocolo offline-first, schemas y modelo in-memory | #22 | Draft. 355/355 Linux y Windows en el HEAD reportado; no demuestra transporte ni persistencia durable. |

### C. Retención y acceso a fuentes

| PR | Entrega | Relación | Disposición |
|---:|---|---|---|
| #75 | CLI de preflight local PowerShell | #71 | CI figuraba pendiente en la descripción; verificar HEAD y CI antes de revisión final. |
| #113 | Corrección documental del estado de política de retención | #71 | Cambio documental acotado; revisar consistencia con el estado operativo NOT_ACTIVE. |
| #114 | Detección de junctions/symlinks ancestros | #71 | CI figuraba pendiente; verificar antes de integrar. |
| #115 | Inventario de artefactos y bloqueo de eliminación incompleta | #71 | CI del último HEAD figuraba pendiente; no declarar borrado seguro ni cobertura de copias externas. |
| #116 | Acceso público BTC/ETH y límites de proveedores | #3/#71 | Documental; candidatos siguen NOT_APPROVED. No habilita RPC ni captura. |

### D. Actor Registry y cadena de procedencia

| PR | Entrega | Dependencia | Disposición |
|---:|---|---|---|
| #78 | Claims multirol por ejecución v1.1 | #77 | CI reportada 322/322; integrar solo después de revisar compatibilidad. |
| #80 | Resolución temporal Actor Registry v1.1 | #79; apilada sobre #78 | CI reportada 350/350; no integrar antes de #78. |
| #82 | Referencias tipadas y resolución temporal de evidencia | #81; apilada sobre #80 | CI no acreditada para el HEAD descrito; verificar/fijar antes de continuar. |
| #84 | Snapshots inmutables y manifiesto offline | #83; depende de #82 | CI reportada 476 pruebas; apilada, no fusionar antes de #82. |
| #86 | Retención por artefacto y exportación estrictamente local | #85; apilada sobre #84 | Revisar políticas y compatibilidad antes de integrar. |
| #87 | Evidencia primaria para políticas de proveedores | #85 y cadena anterior | Mantener bloqueada hasta revisar fuentes primarias y estados PENDING_EVIDENCE. |
| #89 | Intake documental de 20 ámbitos exactos | #88; apilada sobre #87 | CI reportada 504/504; integrar solo después de la cadena anterior. |
| #91 | Captura local y sellado SHA-256 | #90; apilada sobre #89 | CI reportada 518/518; no implica aprobación legal ni descarga de mercado. |
| #93 | Extracción local verificable | #92; apilada sobre #91 | CI reportada 526/526; no sustituye revisión humana del contenido. |
| #95 | Versionado y observación de fuentes normativas | #94; apilada sobre #93 | CI reportada 538/538; no cambia autorización legal. |
| #98 | Afirmaciones documentales con snapshots/cláusulas | #97; apilada sobre #95 | CI reportada 559/559; verificar HEAD y relación con #99. |
| #99 | Hallazgos normativos verificables | #96; apilada sobre #95 | CI reportada 551/551; mantener separada de la semántica de claims documentales de #98. |

La cadena debe revisarse secuencialmente; no se deben fusionar PRs apiladas fuera de orden ni cerrar Issues solo porque una PR hija mencione su número.

### E. Analítica de flujos y exposición

| PR | Entrega | Relación | Disposición |
|---:|---|---|---|
| #107 | Flujos netos por dirección point-in-time | #45 | CI reportada 319/319 Linux y Windows; alcance parcial, no balance ni identidad. |
| #108 | Flujos atribuibles a entidades | #45, #42, #8, #109 | CI no acreditada en la descripción; mantener explícita la limitación BTC UTXO y revisar integración con #110. |
| #110 | Contabilidad BTC UTXO por transacción | #109 | CI reportada 322/322; falta muestra real mainnet y reconciliación. |
| #112 | Exposición histórica con gates de completitud | #111 | CI reportada 328/328; faltan snapshots reales y cobertura de inventario. |

## 6. Problemas de organización detectados

1. **Roadmap y objetivo no están alineados:** el objetivo predictivo oficial está en #23 y PR #24, mientras la hoja de ruta principal conserva texto anterior.
2. **README no cumple función de entrada:** no presenta el producto, estado, arquitectura, ejecución ni límites.
3. **Backlog con Issues posiblemente obsoletas:** #6 y #8 aparecen abiertas aunque la hoja de ruta indica sus contratos integrados mediante PR #7 y #9. #41 también necesita revisión frente a los contratos integrados y sus extensiones #77–#81. No cerrarlas sin comprobar criterios y artefactos.
4. **Prioridad P0 demasiado extendida:** hay muchas tareas de procedencia documental clasificadas P0. La prioridad debe reflejar bloqueo real del producto, no solo rigor técnico.
5. **Cadenas de PR demasiado largas:** la secuencia #82 → #84 → #86 → #87 → #89 → #91 → #93 → #95 → #98/#99 crea un cuello de botella. Cada tramo debe justificar su dependencia estricta y no bloquear tareas independientes.
6. **Separación incompleta entre especificación y entrega:** Issues de señales, contratos, herramientas locales y capacidades operativas comparten etiquetas de prioridad sin una vista de producto.
7. **Métricas sintéticas y muestras reales no siempre se distinguen en la vista de proyecto:** las PR describen los límites correctamente, pero el README/roadmap no ofrece un estado único y visible de la evidencia real disponible.
8. **Ramas auxiliares acumuladas:** el repositorio contiene ramas de trabajo de etapas previas y cadenas abiertas. No deben borrarse sin comprobar si alguna PR o dependencia las utiliza.

## 7. Organización objetivo del repositorio

La estructura documental propuesta es:

```text
README.md
docs/
  product/
    predictive-objective.md
    product-requirements.md
  architecture/
    target-architecture.md
    offline-sync-protocol.md
    persistence-architecture.md
  roadmap/
    implementation-roadmap.md
    release-gates.md
  requirements/
    requirements-register.md
  data-sources/
    provider-due-diligence/
    signal-source-coverage-catalog.md
  data-model/
    source-observation.md
    attribution.md
    trade-execution.md
    entity-flows.md
  predictive/
    target-definitions.md
    dataset-protocol.md
    validation-protocol.md
  audit/
    project-objectives-and-backlog-audit-2026-11-14.md
```

No se propone mover ni renombrar módulos existentes en esta auditoría. La estructura es una organización lógica de documentación; cualquier reorganización física posterior debe evitar romper imports, schemas, fixtures, links y referencias históricas.

## 8. Secuencia de trabajo recomendada

### Fase 1 — Alinear el producto y el backlog

1. Revisar y completar PR #24 para que README, objetivo y arquitectura coincidan.
2. Revisar PR #39 y consolidar el catálogo de señales/fuentes.
3. Reescribir la hoja de ruta para que el objetivo predictivo sea la cabecera y las señales/actores sean inputs.
4. Crear una matriz única de requisitos → Issue → contrato/módulo → pruebas → evidencia real → estado.
5. Revalidar #6, #8 y #41 y cerrar únicamente las que cumplan todos sus criterios.

### Fase 2 — Desbloquear datos reales autorizados

1. Resolver Issue #3 por endpoint, activo y uso permitido.
2. Resolver los gates operativos de #71.
3. Obtener muestras pequeñas BTC y ETH, una ejecución por red, solo después de los gates.
4. Validar hashes, integridad, timestamps, unidades, canonicalidad, calidad y cobertura.
5. Registrar resultados positivos y negativos sin incorporar payloads no autorizados al repositorio.

### Fase 3 — Consolidar el pipeline de inteligencia de actores

1. Revisar la cadena #78 → #80 → #82 y sus pruebas/compatibilidad.
2. Resolver UTXO BTC mediante #109/#110 antes de presentar flujos BTC por entidad como completos.
3. Revisar #107/#108/#112 como componentes parciales y no como capacidades finales.
4. Separar claramente ejecución, transferencia, balance, holding, exposición, control de dirección y beneficiario efectivo.

### Fase 4 — Construir la base predictiva

1. Integrar en orden #24 → #26 → #28 → #30.
2. Definir las features candidatas por familias #31–#37 y #40.
3. Aplicar #36 para comparar cada familia contra baselines y medir valor incremental.
4. Crear datasets point-in-time sin leakage.
5. Ejecutar walk-forward y holdout congelado cuando existan datos reales suficientes.
6. No producir probabilidades operativas hasta calibración y evaluación verificables.

### Fase 5 — Persistencia y experiencia de usuario

1. Cerrar el protocolo real offline-first de #22.
2. Aceptar el ADR de #16 después de requisitos operativos y gates.
3. Implementar almacenamiento durable y recuperación solo tras decisiones verificables.
4. Construir interfaz de evaluación, comparación histórica y seguimiento de ForecastOutcome.
5. Añadir alertas opt-in después de disponer de eventos y fuentes autorizadas.

## 9. Política de cierre y merge

- Una Issue se cierra cuando sus criterios de aceptación están demostrados en `main`, no cuando una PR se abre ni cuando sus pruebas son sintéticas.
- Una PR se integra solo después de revisar diff, base/head, dependencias, CI en el HEAD exacto, conversaciones, compatibilidad y límites de datos.
- Una PR apilada se integra en orden de dependencia; nunca se fusiona una hija para saltarse una base no integrada.
- Una prueba sintética valida comportamiento del software, no exactitud del proveedor, cobertura de mercado ni rendimiento predictivo.
- Los estados `NOT_APPROVED`, `PENDING_EVIDENCE`, `NOT_VERIFIED`, `UNKNOWN`, `NOT_CALIBRATED` y `NOT_ACTIVE` deben conservar su significado.
- No se fusiona una PR solo para reducir el backlog. Tampoco se cierra una Issue por conveniencia estadística.
- No se borran ramas antiguas sin comprobar PRs, dependencias y referencias.

## 10. Limitaciones de esta auditoría

Esta revisión inspeccionó el inventario completo de Issues abiertas y PRs abiertas/no fusionadas, los documentos principales disponibles, las descripciones de entregas y comentarios de estado de las áreas críticas. No equivale a una auditoría exhaustiva línea por línea de los 28 diffs ni a una ejecución de toda la suite desde un checkout local.

Los recuentos y resultados de CI citados son los que aparecen en las evidencias de GitHub revisadas; cada PR debe volver a validarse contra su HEAD actual antes de integrarse. No se han probado datos reales de mercado ni se ha emitido aprobación legal de fuentes.

## 11. Resultado esperado

Al completar esta reorganización, el repositorio debe tener:

- un único objetivo de producto visible y coherente;
- un README que explique qué es IWFI y qué funciona realmente;
- una hoja de ruta única, ordenada por dependencias y valor de producto;
- Issues sin duplicados ni tareas ya completadas;
- PRs apiladas con dependencias explícitas y verificables;
- una separación inequívoca entre contratos, simulaciones, muestras reales y capacidades productivas;
- un camino claro desde datos autorizados hasta predicciones evaluadas científicamente.

**Dictamen:** IWFI tiene cimientos técnicos útiles, pero todavía no ha demostrado su objetivo central con datos reales ni modelos validados. La prioridad organizativa y técnica debe pasar de crear más contratos aislados a alinear la documentación, desbloquear muestras reales autorizadas y completar la cadena predictiva point-in-time y de validación.
