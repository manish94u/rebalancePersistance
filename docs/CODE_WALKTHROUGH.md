# Code Walkthrough

## Verification and Reanalysis

`tools/check_repository.py` reads `provenance/import-manifest.json` and checks
that each imported file still matches its source digest or its explicitly
recorded packaging-fix digest. This protects papers,
figures, recorded data, and simulator source from accidental edits during
packaging. Documented revisions also include venue-neutral front matter and
publication metadata, with separate payload checks protecting all other fields.
Packaging fixes close the legacy tiered setup table with `table`
to match its opening environment, and force the four document build passes
so external references resolve on a clean checkout. Neither changes numerical code.
The checker also invokes the evidence manifest verifier. Rebuilding a PDF
can legitimately change binary bytes; inspect that difference rather than
silently accepting it as a new source archive.

`evidence/reanalyse.py` is the independent analysis entry point:

1. `verify_manifest` checks the exact packaged file set and every digest.
2. `read_rows` reads structured CSV records without modifying them.
3. `paired_rows` rejects duplicate or missing policy/seed combinations.
4. `mean_by_policy` calculates means from episode records, not plot coordinates.
5. `paired_bootstrap` resamples complete episode differences with a fixed seed.
6. `validate_checkpoint` checks shape, frozen mode, and recorded training steps.
7. `infer` performs the stored affine/ReLU/affine calculation without mutation.
8. `analyse` ties the studies to named outputs and checks live receipt totals.

`evidence/test_reanalyse.py` checks corrupt pair handling, saved model shape,
read-only inference, known aggregate values, and live summary consistency.
The archive and these tests are preserved from the reviewer package.

## Reference Simulator

`ScenarioConfig` declares the workload, initial topology, Pod and client rates,
backlog tiers, connection caps, and decision interval. `SimulationEnvironment`
creates subscriptions and connections from this configuration and a seeded RNG.

One `step` first applies the requested action, then generates arrivals and
drains available backlog. It converts delivered interval counts to a per-second
rate, advances the time index, refreshes Pod statistics, and returns metrics.
This ordering matters when interpreting a first-interval intervention.

`observe` exposes client-visible features. Offline metrics may inspect all
subscriptions, while the policy sees active-connection statistics and a probe
sample. `_refresh_pod_stats` aggregates queue state across the Pod's assigned
subscriptions. Count and backlog rebalancing use different objectives.

The reference DQL controller receives transitions and learns during its runs.
It is separate from the frozen deployment checkpoint in `evidence/model/`.
The new public tests check deterministic replay, nonnegative queues, backlog
conservation, subscription ownership, and Pod accounting. These are contract
checks, not a benchmark claiming DQL superiority.

## Manuscript Build and Preservation

`paper/submission-compact/assemble_submission.py` extracts specified source
line ranges and relocates them. It records ownership of labels so cross-file
references use explicit main/supplement prefixes. It does not compute results.

`editorial-bridges.tex` contains the short navigation and summary passages added
when splitting the manuscript. `sections/` contains the extracted body.

`build_submission.py` runs the TeX toolchain for both documents in both orders,
then checks the logs. `verify_relocation.py` compares normalized protected
blocks across the two-document union, so moving a table to the appendix is not
mistaken for deleting it. `inspect_pdf_layout.py` renders pages and checks
geometry; human visual inspection is still needed.

## New Runs and Changes

Use new output directories and manifests for additional experiments. A new
measurement is not a correction to an old measured value. For a genuine bug,
preserve the original data and explain the corrected implementation, changed
estimand, and rerun procedure. See `CONTRIBUTING.md`.
