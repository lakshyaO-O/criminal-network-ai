# Synthetic Data — SIH 26189

All data produced by this generator is **completely fictional**. Names,
phone numbers, account numbers, vehicle registrations, coordinates,
institutions and cases are fabricated. Fictional markers are embedded in
identifiers (`FIC`, `FICA`, `SYN-CASE`, `SYN-FIR`) so synthetic records can
never be confused with real data. No real criminal names, case files, phone
numbers, bank accounts, or personal information are used anywhere.

The system under development is investigator-assistance software; the
synthetic corpus contains **no guilt or criminality labels** — only
entities, relationships, events, and case-linkage metadata.

## Quick start

```powershell
# from repo root
python -m ai.synthetic_data_generator --seed 42 --output data/synthetic

# single combined file instead of per-type files
python -m ai.synthetic_data_generator --seed 42 --single-file
```

Requires Python 3.9+. The AI package is stdlib-only (no pip installs needed).

## Determinism

- Same `--seed` ⇒ byte-identical output, verified by tests.
- `created_at` is derived from the seed (not wall-clock), so even audit
  fields are reproducible.
- `random.Random(seed)` is the only randomness source.

## Output layout (`data/synthetic/`)

| File | Records | Contents |
|---|---|---|
| `persons.json` | 30 | fictional people |
| `organizations.json` | 6 | fictional companies |
| `phone_numbers.json` | 24 | fictional numbers |
| `vehicles.json` | 12 | fictional vehicles |
| `locations.json` | 10 | fictional coordinates |
| `financial_accounts.json` | 14 | fictional accounts |
| `transactions.json` | 45 | transfers incl. demo anomaly |
| `communications.json` | 120 | calls/sms/email/chat |
| `cases.json` | 4 | fictional inquiries |
| `firs.json` | 4 | fictional reports |
| `events.json` | 25 | observed activities |
| `evidence.json` | 8 | metadata-only evidence items |
| `relationships.json` | ~446 | canonical edges + provenance |
| `_generation_config.json` | 1 | seed, counts, patterns |

## Built-in structural patterns

The generator deliberately encodes network shapes that later analytics
(communities, centrality, paths) can operate on:

| Pattern | How it's created |
|---|---|
| Direct relationships | intra-community KNOWS cliques (5-person groups) |
| Indirect relationships | friend-of-friend chains across adjacent communities |
| Communities | persons split into fixed-size fully-connected groups |
| Bridge nodes | first member of each community KNOWS next community's first member |
| Repeated communications | designated pairs exchange ≥6 contacts each |
| Transaction chains | rotating account→account transfer graph + one same-day round-robin burst flagged `is_flagged_demo` |
| Temporal activity | all timestamps spread over a 730-day window; burst confined to one day |
| Unusual behavior (demo) | 6 near-equal amounts cycling through 3 accounts in hours |

## CLI options

```
--seed N               random seed (default 42)
--output DIR           destination (default data/synthetic)
--single-file          write one synthetic_dataset.json
--persons N            override entity counts:
--organizations N      persons, organizations, phones, vehicles,
--phones N             locations, accounts, transactions,
--vehicles N           communications, cases, events
--locations N
--accounts N           (evidence is derived: ceil(num_evidence_target/cases))
--transactions N
--communications N
--cases N
--events N
```

## Safety / PII guarantees

Enforced by `tests/test_synthetic_data.py`:

1. All identifiers carry fictional markers (`FIC`, `FICA`, `SYN-`).
2. Phone numbers use reserved-style fictional ranges only.
3. No record contains real-looking Indian mobile prefixes outside the
   generator's fictional set.
4. No name lists overlap with real case/public-record datasets (names are
   invented combinations from a small fictional pool).
5. Evidence records contain metadata only — no documents, images, or content.
