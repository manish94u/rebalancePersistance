# Main-Paper Reference Restoration

Date: 6 November 2026.

The compact main paper originally cited 25 distinct works. The appendix cited
36; the two-document union retained all 51 works from the reference manuscript.
This revision restores 18 of those works to specific arguments in the main
paper, for exactly **43 explicitly cited references**. The appendix remains at
36 references and the union remains at 51. No bibliography entries were invented,
deleted, or added solely through `\nocite`.

## Placement and Relevance

| Existing citation key | Main-paper context |
| --- | --- |
| `Chen2022RLFeedback` | Prediction-enabled feedback for cloud resource allocation |
| `Chen2023WorkloadWindows` | Workload windows in resource-allocation decisions |
| `Chen2022ActorCritic` | Actor-critic datacenter resource assignment |
| `Caviglione2021VMPlacement` | Selection among placement heuristics versus execution of a transport handoff |
| `Ding2020QLearningCloud` | Cloud dispatch and per-server Q-learning scheduling |
| `Chen2023CollaborativeScheduling` | Heterogeneous workflows with task-continuity constraints |
| `Li2023SparkDRL` | Spark executor allocation with energy and execution-time objectives |
| `Cheng2023PreemptiveCloud` | Preemptive, cost-aware cloud-job scheduling |
| `Liu2026GeoDRL` | Data-intensive task placement with inter-region transfer costs |
| `Sanjalawe2025AIJobScheduling` | Broader AI-based cloud-job scheduling taxonomy |
| `Hortelano2023RLOffloading` | Offloading architectures, objectives, and changing conditions |
| `Huang2020Offloading` | Binary offloading choices in wireless-powered edge computing |
| `Jayanetti2022EdgeCloudScheduling` | Separate tier and node decisions for dependent tasks |
| `Ilager2026DEMon` | Decentralized monitoring quality and resource cost |
| `Gheibi2024AdaptationDrift` | Drift in the quality of available adaptation options |
| `Casimiro2024ModelChecking` | Formal adaptation reasoning, distinguished from runtime handoff guards |
| `Biagiola2022Plasticity` | Adaptation and regression in changed RL environments |
| `Patterson2024EmpiricalDesign` | Performance variability, baselines, tuning, and evaluation bias |

The added text describes each work's relevant control or evaluation problem.
It does not claim that these studies implement our connection protocol or
demonstrate the performance of our controller. Existing stream-processing,
client-side balancing, and closer comparison-table citations remain in place.

## Scope and Preservation

- Only the compact submission copy receives the additional citation context.
- `editorial-bridges.tex` holds the added prose; `assemble_submission.py` places
  it reproducibly in related work and policy validation.
- The original reference manuscript, bibliography database, plot assets,
  measurements, frozen checkpoint, and reviewer evidence remain unchanged.
- The appendix is rebuilt to refresh cross-document references, not its results.
- Imported-file digests record this explicit packaging revision separately from
  original source hashes in `provenance/import-manifest.json`.

## Verification

- Main PDF: 27 pages, including 43 compiled bibliography entries.
- Appendix PDF: 53 pages, including 36 bibliography entries.
- Both documents compile with the local build and built-in editor compiler.
- All 19 offline tests pass; 160 imported files and 48 evidence files pass their
  recorded digest checks. PDF geometry checks find no off-page text or unresolved
  references, and the main-paper page renders were visually inspected.
- A regression test requires 43 distinct main-paper citation keys, each matching
  exactly one bibliography entry, and rejects `\nocite` padding.
- Relocation verification retains all 48 original equation/align blocks, four
  proof-related blocks, 22 tables, 24 figures, three detailed algorithms, and
  all 51 original citation keys, with no unmatched original prose lines.

The original metadata warnings documented in `RELEASE_VALIDATION.md` are not
new findings from this change. Reference restoration does not alter or strengthen
the paper's measured claims.
