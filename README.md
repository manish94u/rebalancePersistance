# Probe-Guided Persistent Connection Rebalancing

Research artifacts for **Probe-Guided Rebalancing of Persistent Subscription
Connections with Greedy and Deep Q-Learning Control**.

The framework makes newly available server capacity reachable to existing
subscriptions. It uses a retained probe connection, partial server telemetry,
and a receipt-gated handoff. Greedy and DQL policies share the same guarded
execution mechanism. The contribution is not a replacement TCP protocol or a
claim that DQL is always better than a well-informed greedy policy.

## Read the Paper

| Document | PDF | Editable source |
| --- | --- | --- |
| Main paper, 25 pages including references | [Main_Manuscript.pdf](paper/submission-compact/Main_Manuscript.pdf) | [Main_Manuscript.tex](paper/submission-compact/Main_Manuscript.tex) |
| Online supplementary material, 53 pages | [Online_Appendix.pdf](paper/submission-compact/Online_Appendix.pdf) | [Online_Appendix.tex](paper/submission-compact/Online_Appendix.tex) |
| Preserved full reference manuscript, 72 pages | [Reference PDF](paper/Rebalancing-Connection-TAAS.pdf) | [Reference source](paper/Rebalancing-Connection-TAAS.tex) |

The compact submission relocates secondary material; it does not change the
recorded results. Its [relocation map](paper/submission-compact/README.md)
and [preservation manifest](paper/submission-compact/relocation-manifest.json)
document that split. These are research submission artifacts, not a claim of
acceptance by ACM TAAS.

## Start Here

Python 3.9 or later is sufficient for the offline checks. No cloud account,
credentials, or Python package installation is needed for these commands.

```bash
git clone https://github.com/manish94u/rebalancePersistance.git
cd rebalancePersistance
python3 -m venv .vnv
source .vnv/bin/activate
python tools/check_repository.py
python evidence/reanalyse.py
python -m unittest discover -s evidence -p 'test_*.py' -v
python -m unittest discover -s tests -p 'test_*.py' -v
```

This verifies preserved files, recomputes paired comparisons from recorded
episodes, checks the saved network, and validates the packaged live receipt
totals. It does not run a new cloud trial or train the model.
The combined command `python tools/validate_release.py` runs these checks plus
manuscript preservation; add `--latex` to rebuild in a disposable copy.

## Replication Routes

| Goal | Start with | What it does |
| --- | --- | --- |
| Recheck the published aggregate results | [Replication guide](docs/REPLICATION.md#1-offline-result-reanalysis) | Recomputes statistics from immutable episode records |
| Inspect the frozen DQL network | [Model card](docs/MODEL_CARD.md) | Loads the saved 21--32--6 network without updating it |
| Run a fresh reference simulation | [Simulator guide](simulator/README.md) | Exercises the independent simulator and its ablations |
| Rebuild the two submission PDFs | [Build instructions](docs/REPLICATION.md#4-build-the-submission-pdfs) | Resolves cross-document citations using vendored ACM files |
| Plan an independent cloud replication | [Cloud protocol](docs/CLOUD_REPLICATION.md) | Defines workload, isolation, telemetry, receipts, and cleanup |
| Trace a result to its data | [Evidence map](docs/EVIDENCE_MAP.md) | Links study design, sample units, and files |
| Understand the implementation | [Architecture](docs/ARCHITECTURE.md), [code walkthrough](docs/CODE_WALKTHROUGH.md) | Explains queues, probes, policies, guards, and analysis |

The archived evidence supports offline reanalysis. The reference simulator is
not the full proprietary cloud client or the deployment-adapter runner used
for every paper experiment. These replication levels are deliberately kept
separate, so a fresh toy run is not mistaken for the paper's locked holdout.

## What the Evidence Shows

| Study | Recorded observation | Scope |
| --- | --- | --- |
| 20,000-subscription cloud deployment | Ten handoffs moved 4,000 subscription bindings; all 20,000 subscriptions were retained over the observation window | Live functional validation |
| Loaded 1,000-subscription DQL trial | Three handoffs, 750 binding moves involving 500 distinct subscriptions; 8,000 deliveries and 8,000 ACK receipts | One live trial, not a replicated throughput comparison |
| Sticky-connection scale-out | Frozen DQL averaged 219,761.67 events/s versus 58,000 for unchanged placement; normalized backlog AUC fell by 12.30% | 20 paired simulator seeds per policy |
| Strong guarded-greedy control | Averaged 221,260 events/s in the same scale-out study | Retained positive comparator, not the random scripted control |
| Mixed workloads | DQL improved composite reward by 0.03179 and subscription-count variance by 90.04%; throughput was 4.50% lower than the heuristic | 40 paired simulator episodes per policy |
| TTL under delivery load | Recorded connection interruptions and incomplete delivery receipts differed between arms | Sequential live comparison; the guarded DQL arm stayed throughout |

Full uncertainty estimates and workload definitions are in the paper and data.
Do not combine the simulator throughput numbers with cloud receipt counts.
In particular, balancing subscription counts does not by itself guarantee a
throughput gain when the client, queue, or another resource is the bottleneck.

## Repository Layout

```text
paper/                       Preserved full manuscript and build dependencies
  submission-compact/        Main paper, online appendix, build/preservation tools
evidence/                    Immutable, redacted reviewer evidence and model
simulator/                   Standalone reference simulator (standard library)
architecture/                Editable historical draw.io architecture sources
docs/                        Replication, architecture, model, evidence guides
tools/                       Repository integrity checks
tests/                       Public simulator invariants and packaging checks
provenance/                  Source-file import checksums
.github/workflows/           Offline validation on push/pull request
```

The older draw.io sources are editable design history. The authoritative
architecture used by the current manuscript is
[`control-architecture-original-style.pdf`](paper/submission-compact/figures/control-architecture-original-style.pdf)
and the handoff description in the main text.

## Publication and Data Handling

This export includes manuscripts, selected figures, redacted numerical evidence,
the frozen checkpoint, and the standalone simulator. It excludes private
client/server source archives, authentication material, subscription OCIDs,
internal endpoints, raw event payloads, and raw cluster logs. No new experiments
were performed as part of exporting the repository.

The historical README inside `evidence/` describes the original reviewer ZIP
before this repository upload. It is retained byte-for-byte for provenance;
this repository README describes the current distribution.

See [contribution rules](CONTRIBUTING.md), [third-party notices](THIRD_PARTY_NOTICES.md),
the [release validation record](docs/RELEASE_VALIDATION.md), and
[citation metadata](CITATION.cff). No new license has been assigned to
author-owned or employer-owned material by this packaging operation.
