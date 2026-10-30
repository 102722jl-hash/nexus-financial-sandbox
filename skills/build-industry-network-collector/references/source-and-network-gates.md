# Source and network gates

## Source tiers

```text
T1  regulator, government, exchange, official API, audited filing
T2  recognized industry body or first-party operating disclosure
T3  reputable third-party structured data
MARKET_PROXY  market signal used as a proxy, not a source fact
```

Reject or quarantine sources with unclear ownership, irreproducible values, prohibited automation, missing timestamps, or no stable locator.

## Evidence requirements

Every observation must resolve through:

```text
observation -> evidence -> raw snapshot -> source registry
```

Require SHA-256, retrieval time, original quote, locator, source tier, acceptance status, and availability time.

## Metric and relationship requirements

Require stable metric identity, description, type, canonical unit, unit family, frequency, entity scope, layer, editable flag, and required flag. Convert units explicitly.

When company entities are in scope, require an explicit entity node for every active company. Instantiate every selected company-scoped metric for every applicable active company. Retain an unobserved node as `DATA_MISSING`; do not drop it or invent a baseline. Connect metric nodes to entity nodes with structural lineage edges that never count as causal propagation.

Require relation endpoints, direction, mechanism, registered formula, parameter status, lag, confidence, impact cap, and invalidation. Weights are positive magnitudes; encode negative influence only with `direction: negative`.

Use `CONFIRMED` for formal calibrated relationships. Use `AI_APPROVED` with `candidate_weight / AI_ASSUMPTION / ABSTAIN`. Never publish `DISABLED`.

## Readiness gates

- `DATA_READY`: valid observation, evidence, metric, and entity references exist.
- `GRAPH_READY`: layers, IDs, endpoints, and formulas are structurally valid.
- `SCENARIO_READY`: an editable node has a supported complete path to a sink node.

Run a real nonzero scenario and require downstream change; a visible line alone is insufficient.

Evaluate the three gates independently. A network is adjustable only when all three are ready. If the confirmed specification uses tiered publication, allow a `GRAPH_READY` network with partial observations to appear as a visibly degraded `GRAPH_PREVIEW`; report `DATA_PARTIAL / GRAPH_READY / SCENARIO_NOT_READY` and disable unsupported downstream propagation. Never publish a network with invalid identity, duplicate IDs, invalid layers, missing endpoints, or an unsupported contract.

Measure baseline coverage separately for all metric nodes and required metric nodes. Use the specification's configurable threshold, defaulting to 80 percent, for `DATA_READY`. Do not count entity aggregation nodes as metric baselines.

Require one batch-wide `data_cutoff`. Preserve `report_period`, `as_of_date`, `published_at`, and `available_at` as the observation's historical timing. A cutoff mismatch must not silently quarantine otherwise valid historical observations.

Quarantine isolated future values, unit-conversion needs, incomplete evidence, and unknown formulas when safe. Block unsupported contract versions, missing network identity, bad hashes, conflicting keys, invalid layers, missing endpoints, missing required metrics, or incomplete source-to-sink paths.
