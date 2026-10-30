# Network versions, entities, and history

Read this reference when a project publishes daily network versions, includes company entities, or displays historical changes.

## Source of truth and versions

The database owns facts, evidence, observations, and revisions. A browser network is an immutable compiled view of one validated batch cutoff. Collectors write standard batches or database rows; only the validated compiler publishes browser networks.

Create a new unique internal network ID when the compiled content or batch changes. Preserve old versions for rollback and never auto-switch the network already open in the browser. Use `created_at` as the upload/generation timestamp and `data_cutoff` as the information boundary.

Display the version using the configured local timezone:

```text
one version on a date       -> YYYY-MM-DD
multiple versions on a date -> YYYY-MM-DD HH:mm
same-minute collision       -> YYYY-MM-DD HH:mm:ss
```

The displayed date is not a primary key. Loading, deletion, and rollback continue to use the internal ID.

## Entity and node completeness

When company entities are in scope:

- generate one explicit `ENTITY` node for each active company;
- instantiate each selected company-scoped metric for every applicable active company;
- retain missing observations as nodes with `DATA_MISSING` and no fabricated baseline;
- connect company metric nodes to their entity with `CONFIRMED_LINEAGE / ENTITY_METRIC` structural edges;
- exclude structural edges from causal propagation and scenario edge counts.

Do not infer company identity from labels or metric types. Use the canonical entity code.

## Historical observations and changes

Expose eligible historical observations to the browser. A company model should be able to show the latest value, previous-value change, report period, update or availability time, source, evidence status, and a trend when two or more valid observations exist.

Compute change only within this partition:

```text
entity_code + metric_code
```

Sort by the observation's business time, then compare with the immediately previous valid observation. Preserve revisions and choose the accepted revision deterministically. Missing or rejected rows do not become comparison baselines.

Recommended history windows are 30 days, 90 days, 365 days, and all history. They are configurable UI choices, not deletion policies.

## Date semantics

Every observation in an exported batch uses the enclosing batch's `data_cutoff`. Preserve the real historical timing separately in `report_period`, `as_of_date`, `published_at`, `available_at`, and linked evidence. Do not rewrite historical business dates to the batch date.

## Tiered publication

Use three observable outcomes:

```text
GRAPH_BLOCKED   structural identity, layer, endpoint, or contract failure; do not list
GRAPH_PREVIEW   GRAPH_READY with partial data; list only with degraded state visible
SCENARIO_READY  DATA_READY + GRAPH_READY + SCENARIO_READY; allow supported adjustment
```

A preview must report baseline coverage, keep unsupported calculations disabled, and retain `ABSTAIN`. A network becomes scenario-ready only after a real nonzero upstream change produces a downstream change on a supported path.

## Verification

Test at least:

- unique internal IDs and date-based display labels;
- same-day display disambiguation;
- old-version loading and rollback;
- explicit entity nodes and structural edges;
- complete per-entity metric instantiation with honest missing nodes;
- historical rows surviving repeated ingestion;
- same-entity/same-metric previous-value comparison;
- batch cutoff consistency with historical dates preserved;
- preview publication without unsupported propagation;
- nonzero editable-to-sink scenario propagation before scenario-ready status.
