# Reviewer Evidence: Probe-Guided Connection Rebalancing

This is the offline evidence companion to the manuscript. It contains recorded
measurements, protocol metadata, the frozen network weights, and a dependency-free
reanalysis script. It does not contact Oracle Cloud or publish events.

## Run the checks

Use Python 3.9 or later. No external packages are required.

```bash
python3 reanalyse.py
python3 -m unittest test_reanalyse.py
```

The first command verifies every packaged file against `MANIFEST.json`, checks
paired episode coverage, recomputes policy means and selected relative effects,
and checks the October trial's subscription and receipt totals. It prints JSON
to standard output. The empirical records are not modified.

The script also reports a paired bootstrap interval for the DQL-minus-greedy
scale-out throughput contrast using a fixed analysis seed. This is an explicitly
labelled reanalysis of existing episodes, not a new experiment or a replacement
for the original registered DQL-minus-unchanged-placement test. Original paired
analyses and their protocols remain in `data/`.

## Data map

| Directory | Evaluation unit and purpose |
| --- | --- |
| `data/v3` | 40 paired mixed-workload episodes per policy; training and selection records |
| `data/persistent-scaleout-recovery-complete` | 20 paired seeds per policy; 20,000 subscriptions; interval trajectories and registered analysis |
| `data/adverse-probe-ablation` | Separate 30-seed inference and five-seed scale cohorts; do not pool them |
| `data/adhoc-migration-sensitivity` | Independent scripted schedules evaluated on the original scale-out seed bank; exploratory |
| `data/v4`, `data/v5`, `data/v6` | Completed development diagnostics; not additional holdout results |
| `data/live-dql-20261026` | One loaded Oracle Cloud trial; anonymous Pod labels, handoff durations, ACK curve, and topology |
| `data/ttl-preload-20260925`, `data/ttl-loaded-20260925` | Separate aggregate live TTL comparisons |
| `model` | Frozen 21--32--6 network and the loaded trial's observation/guard settings |

`model/frozen-policy.json` is the original frozen file, not retrained weights.
Its SHA-256 is `3e68371d848eca85ec0b87c7c7dd831ea3ec953e2c1bd51c0d79871c7ef3e1e1`.
The absent action-contract field identifies the legacy open-only scale-up
contract. The October trial explicitly disabled both scaling actions. Do not
load this file into an unrestricted newer action executor.

To inspect inference without a transport or cluster:

```bash
python3 reanalyse.py --features '[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]'
```

Outputs follow the order `stay, rebN, rebG, scale+, scale-, migrate`. A Q-value
alone does not authorize an action; feasibility masks and execution checks are
outside this inference utility.

## Access and limits

This ZIP is prepared for attachment as reviewer supplementary material. It has
not been uploaded or published by the agent. The manuscript source and this
archive must be submitted together for reviewers to receive the stated access.

The package permits offline reanalysis and frozen-network inference. It is not
a complete independent rerun of the proprietary service or the simulator's
transport adapter. Cluster credentials, internal endpoints, raw subscription
identifiers, event payloads, and private server/client source archives are not
included. Raw cluster access is not required for these checks, and no public
access to restricted records is promised.

Aggregate files preserve numerical measurements. For selected JSON/CSV metadata,
absolute local paths are replaced by a basename-only restricted-reference
marker; `PROVENANCE.json` records source and packaged hashes and whether this
metadata transformation occurred. The original records remain unchanged in the
author archive. A checksum proves file consistency, not experimental validity.

Receipt reconciliation measures the client-observed STOMP ledger. It is not
an exactly-once CloudEvent identity audit or proof of backend queue deletion.
Simulator rates describe the declared model, not measured Pod capacity.
