# Replication Guide

## Scope and Prerequisites

Run commands from the repository root unless a command explicitly changes
directory. Use Python 3.9 or later and a virtual environment named `.vnv`.
The checked-in evidence and frozen weights must not be overwritten by new runs.
Publication metadata is venue-neutral. Original and packaged hashes document
the metadata-only changes; numerical measurements are unchanged.

```bash
python3 -m venv .vnv
source .vnv/bin/activate
```

There are three distinct activities:

1. **Reanalysis:** recompute a statistic from existing recorded episodes.
2. **New simulation:** execute a model and create new synthetic trajectories.
3. **Cloud replication:** run a real service, load generator, and clients in an
   isolated, authorized deployment.

The first is fully offline here. The second is available through the reference
simulator, with the scope described below. The third requires the service and
authorized infrastructure; it is not executed by any public quick-start command.

## 1. Offline Result Reanalysis

```bash
python tools/check_repository.py
python evidence/reanalyse.py
python -m unittest discover -s evidence -p 'test_*.py' -v
```

`check_repository.py` compares the imported files with their source or explicitly
documented repository-revision hashes and
checks that the frozen network has not changed. `reanalyse.py` verifies the
exact evidence file set, rejects missing/duplicate pairs, and reports JSON.
The evidence directory currently contains 48 manifest-covered files plus the
manifest itself. Interpreter cache files are ignored.

Expected key values, allowing ordinary floating-point rounding:

| JSON field / quantity | Expected |
| --- | ---: |
| Network parameters per network copy | 902 |
| Scale-out FrozenDQL mean throughput | 219761.6666666667 events/s |
| Scale-out unchanged-placement mean throughput | 58000 events/s |
| Scale-out guarded-greedy mean throughput | 221260 events/s |
| DQL / unchanged-placement throughput ratio | 3.7889942529 |
| Backlog-AUC reduction versus unchanged placement | 12.3027976673% |
| Mixed-workload DQL-minus-heuristic reward | 0.0317893048 |
| Loaded live trial consistency checks | true |

The reported bootstrap of DQL-minus-greedy scale-out throughput is a labelled
reanalysis, not the registered primary contrast. It uses 10,000 resamples and
analysis seed 20261027. Episodes, not individual interval samples, are the
paired resampling unit. The original registered analyses remain in `evidence/data/`.

To save a new report without changing the archive:

```bash
mkdir -p results
python evidence/reanalyse.py > results/reanalysis.json
```

The `results/` directory is ignored by Git. Record the Git commit and Python
version with any report intended for independent comparison.

## 2. Frozen Network Inference

```bash
python evidence/reanalyse.py --features '[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]'
```

The zero vector is an interface check, not an operational workload. Provide
21 finite, correctly normalized features to inspect another state. The feature
order is in Appendix D and `paper/model-implementation-appendix.tex`.

Outputs are ordered `stay, rebN, rebG, scale+, scale-, migrate`. These are
action values, not probabilities or permissions. The utility does not apply
freshness guards, resolve a concrete subscription, or mutate a connection.
See [MODEL_CARD.md](MODEL_CARD.md) before integrating the checkpoint elsewhere.

## 3. Reference Simulator

First run the fast, independent invariants:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Then run a short end-to-end simulation:

```bash
python simulator/run_experiments.py --steps 20 --seeds 1
```

The runner executes three workloads and twelve controller/ablation variants.
It writes CSV files and LaTeX fragments below `simulator/output/`. It does not
edit `evidence/` or the paper. A short run checks plumbing; it is not a
convergence study.

Longer exploratory runs use:

```bash
python simulator/run_experiments.py --steps 3000 --seeds 5
python simulator/run_experiments.py --steps 10000 --seeds 5
python simulator/run_tiered_backlog_experiment.py --steps 3000 --seeds 3
```

The implemented deterministic seed bank has ten entries. Use `--seeds` from
1 through 10; requests above ten do not create extra seeds in this preserved
runner. Both runners write to fixed output locations, so archive prior outputs
outside that directory before starting another run. Never relabel an exploratory
run as a locked holdout result.

The tiered scenario assigns 20,000 subscriptions equally to initial backlogs
100,000, 50,000, 5,000, and zero. This gives 775,000,000 logical queued events.
Those are simulator quantities, not permission to enqueue that volume in a
400 MB cloud queue. Fanout multiplies queue copies by matching subscriptions.

**Version boundary:** these standalone runners predate the deployment-adapter
training/evaluation harness used for the paper's later locked studies. They
exercise queue dynamics and controller ablations, but they are not a command
to reproduce every later frozen-policy table from scratch. The latter tables
can be reanalysed from the shipped episode data. The private transport adapter
and cloud implementation are not included in this publication export.

## 4. Build the Submission PDFs

Install a TeX distribution providing `latexmk`, `pdflatex`, `bibtex`, and the
packages referenced by the two `.tex` preambles. The ACM class and bibliography
style are vendored. Then run:

```bash
cd paper/submission-compact
python3 build_submission.py
python3 verify_relocation.py
```

The script builds appendix/main/appendix/main so both external reference sets
resolve. Each pass is forced because a clean checkout has no external `.aux`
dependency for `latexmk` to discover initially. It rejects unresolved
references, duplicate labels, and overfull boxes.
The checked-in PDFs are 25 and 53 pages respectively. Do not reduce margins or
fonts to alter the page count. A different TeX installation can produce
different PDF bytes even when the content and pagination agree.

`verify_relocation.py` checks the unchanged reference source, 25 assets,
48 equation/align blocks, four theorem/proof blocks, 22 tables, 24 figures,
three detailed algorithms, and all 51 originally cited reference keys.

To repeat the original structural extraction, run the following **only when
intending to regenerate the section files**:

```bash
python3 assemble_submission.py
python3 build_submission.py
python3 verify_relocation.py
```

The assembler overwrites generated section files. Keep editorial changes in
the assembler and `editorial-bridges.tex` when using this workflow. Do not edit
the preserved parent manuscript to make a check pass.

For visual inspection, install `pdfplumber`, Pillow, and Poppler (`pdftoppm`),
then run `python3 inspect_pdf_layout.py` in this directory. It renders every
page, creates contact sheets under `tmp/pdfs/`, and checks page boundaries and
unresolved-reference markers. Review the rendered pages as well as the checks.

Known existing BibTeX metadata warnings for `Krasowski2023ProvablySafe` and
`Dong2020CloudManufacturing` are preserved; missing fields were not guessed.

To run all checks and rebuild in a disposable copy without changing the
checked-in PDFs, use `python tools/validate_release.py --latex` from the
repository root. Omit `--latex` when the TeX toolchain is unavailable.

## 5. Cloud Replication

Follow [CLOUD_REPLICATION.md](CLOUD_REPLICATION.md). No credential, OCID, host,
container registry, or private service implementation is bundled. New cloud
trials should have their own protocol, trial IDs, seeds, initial state, storage
budget, and immutable evidence manifest. Do not overwrite historical records.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Evidence checksum mismatch | Inspect the changed file with Git. Do not regenerate the manifest merely to silence the error. |
| `ModuleNotFoundError: reanalyse` | Use the exact unittest discovery command above from the repository root. |
| `latexmk` missing | Install the TeX toolchain and put its binaries on `PATH`. |
| `??` in PDF references | Build both documents with the supplied build script. |
| Simulator run is slow | Start with 20 intervals and one seed; the tiered run tracks individual subscriptions. |
| New model does not match the saved result | Confirm checkpoint digest, action contract, feature order, seeds, and training/frozen mode. |
| Need full service deployment | Obtain authorized access independently; the public evidence package is not a server distribution. |
