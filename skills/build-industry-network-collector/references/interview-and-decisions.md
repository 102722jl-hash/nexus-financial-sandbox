# Interview and decision flow

## Purpose

Collect enough information to build the correct network without overwhelming the user. Ask one to three related questions per turn and summarize confirmed choices before moving forward.

## Rounds

### Round 1: Network outcome

Ask what industry or sector to cover, which geography/market/entities are in scope, and what final outcomes the network must explain. Offer operating volume, revenue, cost, profit, cash flow, valuation, and market price as common outcome choices.

### Round 2: Metric selection

Propose a complete candidate matrix instead of asking the user to invent metrics. Cover external drivers, supply/demand, price/cost, operations, financials, and result nodes.

For each metric capture:

```text
metric_code, metric_name, reason, canonical_unit, frequency,
entity_scope, default_layer_code, editable_default,
required_for_network, selection
```

Use `REQUIRED / OPTIONAL / PROXY_ALLOWED / EXCLUDE` for selection.

### Round 3: Source selection

For each required metric provide up to three current source options. Ask the user to choose primary and fallback sources. If no lawful reproducible source exists, offer a proxy or remove the metric; never pretend a source is available.

### Round 4: Automation

Confirm frequency, local time, timezone, workday/holiday behavior, retries, historical backfill, revision handling, notifications, and retention.

### Round 5: Database and security

Default to one `nexus_networks` database, one schema per industry, one schema writer, and one network-only readonly role. Ask for `AUTO_GENERATE_LOCAL`, `USER_ENV`, or `SECRET_MANAGER`; never ask for a plaintext password in chat.

### Round 6: Publication

Confirm that passing batches publish to the network list, old versions remain available, and the browser does not auto-switch. Confirm whether any metric or relationship requires extra manual approval.

## Decisions agents must not guess

- paid-source budget or authenticated scraping;
- legal permission when terms are unclear;
- live host or production credentials;
- destructive replacement of an existing schema;
- notification recipients;
- whether backfill may consume paid quotas;
- promotion from candidate to formally identified causal relationship.

## Resume behavior

If `config/domain_spec.json` exists, read it first. Ask only about `UNDECIDED`, invalid, or newly contradicted fields. Never repeat completed rounds.

