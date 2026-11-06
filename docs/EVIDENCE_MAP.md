# Evidence-to-Result Map

All paths below are relative to `evidence/`. The archive is immutable and its
`MANIFEST.json` covers 48 files. `PROVENANCE.json` records original versus
packaged hashes, metadata redactions, and venue-neutral metadata revisions.
Checksums establish consistency, not
the truth of a scientific claim.

| Study | Data and protocol | Unit / comparison | Interpretation |
| --- | --- | --- | --- |
| Mixed-workload holdout | `data/v3/holdout-episodes.csv`, `holdout-manifest.json`, `overall-paired-tests.csv` | 40 paired episodes per policy; ten seeds across four scenarios | Frozen DQL, heuristic, static; retain all metrics |
| Persistent scale-out | `data/persistent-scaleout-recovery-complete/episode-metrics.csv`, `registered-protocol.json`, `primary-effect.json` | 20 paired seeds for three policies | One-to-four-Pod capacity with sticky initial connections; simulator |
| Adverse probe | `data/adverse-probe-ablation/episode_metrics.csv`, `registered-protocol.json`, `paired_auc_effects.csv` | 30-seed inference cohort and separate five-seed scale cohort | Guarded versus forced/blind promotion; do not pool cohorts |
| Ad-hoc scripted timing | `data/adhoc-migration-sensitivity/combined-episode-metrics.csv`, `registered-extension.json`, `paired-effects.json` | 20 paired seeds per displayed policy | Exploratory fixed/jittered schedules, not the strong greedy selector |
| 20,000-subscription live handoff | `data/live-20000/handoff-durations.csv` plus paper's aggregate accounting table | Ten handoffs | Duration records do not contain the full raw event ledger |
| Loaded 1,000-subscription DQL | `data/live-dql-20261026/manuscript-summary.json` | One loaded trial, three actions | Topology, preserved sessions, 8,000 deliveries/ACK receipts |
| Preloaded TTL comparison | `data/ttl-preload-20260925/manuscript-summary.json` | Sequential live arms | TTL interruptions and completion, not a replicated DQL throughput win |
| Separate loaded TTL comparison | `data/ttl-loaded-20260925/manuscript-summary.json` | Separate live workload | Do not merge with preloaded trial |
| Development diagnostics | `data/v4`, `data/v5`, `data/v6` | Candidate/contract development | Not extra locked holdout samples |
| Frozen model | `model/frozen-policy.json`, `model/loaded-trial-settings.json` | One archived candidate plus deployment restrictions | Read-only inference; feature/action contract matters |

## Policy Name Mapping

| Archived identifier | Meaning |
| --- | --- |
| `FrozenDQL` | Frozen learned selector with deployment guards |
| `KubernetesScaleOutOnly` | Added ready Pods, no movement of existing subscription-bearing sockets |
| `ScriptedProbeMigration` | Strong pressure-aware guarded-greedy actuator control in the scale-out dataset |
| `AdHocFixed40s`, other `AdHoc...` names | Pressure-unaware scripted schedules, with the timing rule encoded in the identifier |
| `Heuristic` | Threshold-based comparator in the mixed-workload holdout |
| `Static` | Unchanged assignment in that holdout |

Do not rename `ScriptedProbeMigration` to a random jittered policy. Use both the
stored identifier and its descriptive meaning when writing a new table.

## Metric Calculations

- **Throughput:** completed/delivered event count divided by the declared
  observation duration; check each dataset's definition before comparing.
- **Relative throughput change:** `100 * (mean_DQL / mean_baseline - 1)`.
- **Normalized backlog AUC:** trapezoidal time integral of `B(t)/B(0)`, divided
  by the observation duration. Smaller values mean less accumulated exposure.
- **AUC reduction:** `100 * (1 - mean_AUC_DQL / mean_AUC_baseline)`.
- **Connection count variance:** variance of subscription counts across one
  client's active connections, not across all cluster Pods.
- **Connection backlog variance:** variance of cumulative queue backlog across
  those connections. Better count balance does not imply better backlog balance.
- **ACK reconciliation:** compare client-observed delivery and receipt totals;
  this is distinct from a unique-event loss audit and backend deletion proof.

Keep paired seeds together when bootstrapping. Do not treat all intervals from
the same episode as independent replicates. The paired interval estimates and
analysis seeds shipped with the studies remain the reference calculations.

## Plot Provenance

Published plot PDFs are included unchanged under `paper/figures/` and
`paper/submission-compact/figures/`. The compact manuscript preserves their
values and captions. A new plot must identify its source study and compute all
dimensions from that study; do not mix one study's throughput with another
study's radar axes. No historical figure was regenerated during this export.
