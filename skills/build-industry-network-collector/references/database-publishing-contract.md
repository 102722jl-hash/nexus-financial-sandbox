# Database and publishing contract

## Architecture

Use one PostgreSQL service and normally one `nexus_networks` database. Isolate each industry in a sanitized lowercase schema. Create `<schema>_writer` and `<schema>_network_readonly`.

The writer ingests validated batches. The readonly role is the browser identity and receives `SELECT` only on network publication views.

## Readonly-visible objects

Expose exactly these views by default:

```text
published_networks
published_layers
published_nodes
published_edges
published_metric_values
published_evidence
```

The browser lists versions from `published_networks` and loads other views by `network_id`. `published_metric_values` exposes all eligible historical observations for the selected network, not only each metric's latest value. A conforming schema does not require manual table or field selection.

Never grant readonly access to raw documents, source registry, ingestion runs, quarantine, credentials, logs, pending mappings, rejected observations, or unpublished formulas/relationships.

## Publication filters

- Block structurally invalid networks. Publish graph previews only when the specification explicitly enables tiered publication and expose their degraded readiness state.
- Publish active layers and non-disabled nodes.
- Publish only validated edge endpoints and formulas. Include zero-weight `CONFIRMED_LINEAGE` structural edges such as `ENTITY_METRIC`, but never use them for causal propagation.
- Publish `AI_APPROVED` edges only with positive `candidate_weight`; keep `ABSTAIN`.
- Publish observations only when evidence, cutoff, unit, and quality checks pass.
- Expose evidence required by both current node baselines and eligible historical observations: quote, locator, time, tier, and hash, never raw response bodies.

## Credential policy

Allow `AUTO_GENERATE_LOCAL`, `USER_ENV`, or `SECRET_MANAGER`. Store only references such as `STORAGE_PG_WRITER_PASSWORD`, never secret values.

## Idempotency and versions

Use stable observation IDs and `ON CONFLICT`; never truncate an industry schema during routine collection. Preserve snapshots/evidence, append observations, use revisions for corrected facts, create a new immutable network version when content changes, and keep rollback targets.

Keep the internal `network_id` unique and stable for API loading, deletion, and rollback. The browser label is presentation metadata: show the generation date in the configured timezone, add hours and minutes when a date has multiple versions, and add seconds only when needed to disambiguate the same minute. Never replace the internal ID with a date-only key.

For company history, compare an observation only with the previous valid observation having the same `entity_code` and `metric_code`. Do not compare arbitrary adjacent rows or values belonging to different entities.
