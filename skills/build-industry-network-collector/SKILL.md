---
name: build-industry-network-collector
description: Interactively design and implement a reusable industry data-collection and transmission-network project. Use when a user wants to choose an industry or sector, decide which web/API/CSV/PDF data to collect, compare sources, define collection schedules and backfills, create an isolated PostgreSQL schema and least-privilege roles, normalize evidence and metrics, generate network nodes/formulas/relationships, validate propagation, or publish a new network to the NEXUS browser.
---

# Build Industry Network Collector

Guide the user from an industry idea to an auditable scheduled collector, PostgreSQL schema, and adjustable transmission network. Keep causal claims conservative and every published node traceable to evidence.

## Operating defaults

Apply these defaults unless the user explicitly changes them:

- Use one PostgreSQL database, normally `nexus_networks`, with one isolated schema per industry.
- Create a schema-scoped writer role and a network-only readonly role.
- Grant readonly access only to the six published views in `references/database-publishing-contract.md`; never grant raw tables.
- Treat the database as the fact and history system of record; treat each browser network as an immutable compiled view of one validated batch cutoff.
- Append observations and revisions instead of replacing history. Preserve batches and network versions for rollback.
- Block structurally invalid networks. When the confirmed specification allows tiered publication, a `GRAPH_READY` network with partial data may appear only as an explicitly labeled preview; it must not be labeled `SCENARIO_READY`.
- Never replace or switch the network currently open in the browser.
- Treat `AI_APPROVED` relationships as candidate propagation with positive `candidate_weight`, `AI_ASSUMPTION`, and `ABSTAIN`.
- Keep internal network IDs unique. Display the generation date in the browser, adding local time when multiple versions share a date.
- Never request, print, log, or write a plaintext password in chat or project files.

## Conversation workflow

Ask only one to three related questions per turn. Reuse answers already supplied and do not restart the interview.

### 1. Establish the network purpose

Ask for industry, geography, market scope, network type, entities, and final outcomes such as sales, revenue, cost, profit, cash flow, valuation, or market price.

Do not design sources before the intended source-to-result path is clear. Read `references/interview-and-decisions.md` for the question order.

### 2. Propose a metric matrix

Analyze the sector and propose metrics across:

```text
external drivers -> supply/demand -> price/cost -> operations -> financials -> valuation/results
```

For each metric show name, purpose, unit, frequency, entity scope, layer, editable flag, and whether it is required for an end-to-end path. Ask the user to classify it as `REQUIRED`, `OPTIONAL`, `PROXY_ALLOWED`, or `EXCLUDE`.

Keep at least one editable source metric and one sink/result metric.

### 3. Compare sources

Search current official documentation and source sites when tools permit. Offer two or three realistic choices per required metric and explain publisher, URL, tier, access method, cost, history, frequency, license/robots/login/rate limits, evidence quality, and fallback.

Prefer official APIs, regulators, exchanges, company announcements, and structured downloads. Do not promise scraping before confirming access is permitted. Apply `references/source-and-network-gates.md`.

### 4. Confirm automation and history

Ask for frequency, local time, timezone, workday/holiday behavior, retries, historical backfill, revision handling, notifications, retention, browser version-label timezone, and whether graph-only previews may be published. When company entities are in scope, confirm the history windows shown in the company model. Default to a dry run before installing a schedule.

### 5. Confirm database and credentials

Derive a lowercase schema code and propose:

```text
<schema>_writer
<schema>_network_readonly
```

Ask for `AUTO_GENERATE_LOCAL`, `USER_ENV`, or `SECRET_MANAGER`. Never ask the user to paste an actual password. Store only environment-variable names or secret references.

The readonly role must see only published network views. A conforming project lets the browser load those views without asking the user to select tables or fields.

### 6. Record and validate the specification

Copy `assets/domain-spec.template.json` into the target project, replace every example value, and record rejected choices in `decisions`.

Run:

```text
python scripts/validate_domain_spec.py <domain-spec.json>
```

Do not create a database, schedule, or live collector while blocking issues remain.

### 7. Scaffold and implement

After confirmation, run:

```text
python scripts/scaffold_domain.py <domain-spec.json> --output <project-directory>
```

Implement one adapter per selected source:

```text
fetch -> snapshot -> extract -> validate -> commit -> report
```

Reuse the NEXUS crawler contract and compiler in the workspace when available. Do not modify frozen versions. Do not let collectors write browser files directly; publish through the validated compiler.

### 8. Verify the complete path

Before scheduling, verify:

- snapshot hash and reproducible locator;
- document -> evidence -> observation references;
- canonical units and date semantics;
- stable IDs and repeated-ingestion idempotency;
- expected node counts and layer assignments;
- explicit entity nodes for in-scope companies, complete per-entity metric instantiation, and `DATA_MISSING` nodes instead of silent omission;
- structural entity/data-lineage edges kept separate from causal propagation edges;
- endpoint and registered-formula validity;
- positive weight magnitude, with sign only in `direction`;
- an editable node reaching a sink;
- a real scenario producing downstream changes;
- batch-wide cutoff consistency while preserving each observation's report, publication, availability, and as-of dates;
- historical observations remain queryable and same-entity/same-metric changes use the previous valid observation;
- readonly denial for raw, quarantine, credential, and log tables;
- published views returning only eligible rows.

Keep `DATA_READY`, `GRAPH_READY`, and `SCENARIO_READY` independent. Require all three before labeling a network adjustable and scenario-ready. A configured preview may be listed with `DATA_PARTIAL / GRAPH_READY / SCENARIO_NOT_READY`; make the degraded state visible and disable unsupported propagation. Quarantine local failures when safe; block broken identities, hashes, layers, endpoints, or complete paths.

### 9. Publish and schedule

Publish a versioned network to the browser list at the approved readiness tier. Keep the previous active version and report the new internal ID, display date, counts, baseline coverage, path coverage, readiness states, warnings, and rollback target. Do not auto-switch.

Install the schedule only after a successful dry run and confirmation of time and timezone.

## Required deliverables

Produce or update:

```text
config/domain_spec.json
config/runtime.example.env
database/published_views.sql
collector/source_adapters.py
network/network_blueprint.json
scheduler/schedule.json
reports/scaffold_report.json
standard_batches/
snapshots/
tests/
```

Report what is implemented, what remains a candidate, what needs credentials, and what has not been applied to a live database.

## Resource routing

- Read `references/interview-and-decisions.md` before starting or resuming an interview.
- Read `references/database-publishing-contract.md` before schemas, roles, views, grants, or browser import logic.
- Read `references/source-and-network-gates.md` before approving sources, formulas, relationships, or publication.
- Read `references/network-version-and-history.md` before implementing entity nodes, daily network versions, company history, change comparisons, or tiered browser publication.
- Use `assets/domain-spec.template.json` as the canonical requirements record.
- Use `assets/published_views.template.sql` to expose only network-ready content.
- Run `scripts/validate_domain_spec.py` before `scripts/scaffold_domain.py`.
