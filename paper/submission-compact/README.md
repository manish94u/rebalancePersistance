# Compact Submission Copy

Prepared on 4 November 2026. This directory is separate from the reference
manuscript. No parent source, figure, measurement, bibliography, or PDF was
modified.

## Deliverables

- `Main_Manuscript.pdf`: 25 pages, including references.
- `Online_Appendix.pdf`: 53 pages, including its contents and references.
- The corresponding `.tex` files and `sections/` directory are editable.
- `reviewer-evidence.zip` is an unchanged copy of the existing redacted
  reviewer artifact, not a new experimental run or a complete deployment rerun.

The reference manuscript remains 72 pages in the parent directory. Both new
documents retain `acmart` manuscript format. Body font size, margins, line
spacing, plotted values, and original figure assets have not been reduced or
altered to meet the length target.

## Editorial Scope

This is primarily a relocation, not a rewrite. Original passages are extracted
by `assemble_submission.py`. The short navigation sentences, TTL and ablation
summaries, and compact control-loop algorithm are isolated in
`editorial-bridges.tex`. Original detailed algorithms remain in the supplement.

The main paper retains the shared greedy/DQL framing, retained-probe architecture,
receipt-gated protocol, core mathematical definitions, 20,000-subscription
Oracle Cloud trial, loaded 1,000-subscription DQL trial, scale-out comparison,
and mixed-workload result table. The measured boundaries remain explicit:
simulator performance is not relabelled as cluster throughput; the TTL-disabled
arm stayed under its telemetry guards; the strong guarded-greedy comparator
remains distinct from the random scripted schedules.

Some short definitions, tables, and interpretation passages appear in both
documents so the main results and the detailed supplement remain readable.
This accounts for the combined length exceeding the reference manuscript.

## Relocation Map

| Reference material | Main paper | Online supplement |
| --- | --- | --- |
| Introduction and contributions | Retained | No replacement text |
| Related work | Persistent messaging, stream processing, autonomic control, comparison table | E: broader cloud and edge literature |
| System model | Core architecture and complete handoff protocol | F: original component descriptions and overview figure |
| Mathematical formulation | Queue/backlog definitions, observation boundary, imbalance, pressure, reward | A: reference scales, global objective, complete proofs; B: notation |
| Runtime algorithms | Policy roles, Q-learning equations, configuration, compact control loop | C: complete sizing, rebalancing, DQL algorithms, checkpoints and diagrams |
| Neural input specification | Configuration table and pointer | D: exact feature order, normalization, thresholds |
| 20,000-subscription deployment | Setup, aggregate results, event accounting | G: paired timing plot and detailed interpretation |
| 2,000-subscription calibration/startup | Pointer only | H: full text, results and plots |
| Loaded 1,000-subscription DQL trial | Full trial, table and placement/ACK figure | Referenced from the extended interpretation |
| TTL comparison | Two-paragraph measured-outcome summary | I: complete implementation, recovery definitions, trials, tables and plots |
| Primary scale-out simulator | Workload, service assumptions, method, results, backlog figure | J: additional capacity plots, violin distributions and timing-control study |
| Mixed-workload and adverse-probe studies | Selection protocol, mixed result table, ablation summary | K: complete study designs, diagnostics, all detailed comparisons |
| Later action-contract studies | Scope and version boundary retained | L: complete development diagnostics |
| Discussion/conclusion | Core interpretation | M: full original interpretation |

Supplement figures, tables, algorithms and equations use an `S` prefix.
Cross-document references name the destination explicitly and link to the
other PDF. Keep the two PDFs together for relative-file links to work; their
printed references remain understandable when uploaded separately.

## Build and Verify

From this directory:

```bash
python3 build_submission.py
python3 verify_relocation.py
```

`build_submission.py` uses the vendored class/style, builds both files twice
as necessary for external references, and rejects unresolved references,
multiply defined labels, and overfull boxes. It does not write into the parent
directory. The local TeX installation must provide `latexmk`, `pdflatex`, and
`bibtex`.

To repeat the extraction from the untouched reference version:

```bash
python3 assemble_submission.py
python3 build_submission.py
python3 verify_relocation.py
```

Re-extraction overwrites the generated TeX files in this directory. Therefore,
make further extraction changes in the assembler or editorial bridge file, or
do not re-extract after manually editing generated sections. A source hash
mismatch stops extraction and requires review rather than silently accepting
a changed parent manuscript.

For visual QA, use a Python environment with `pdfplumber` and Pillow and an
installed `pdftoppm`:

```bash
python3 inspect_pdf_layout.py
```

Rendered pages/contact sheets are under `tmp/pdfs/`. They are review aids, not
submission files. Both documents were also checked with the built-in editor
compiler without replacing the open reference document.

## Preservation Checks

`relocation-manifest.json` records source ranges and checksums.
`preservation-check.json` verifies the two-document union:

- 14 original source/PDF files unchanged.
- 25 copied assets byte-identical, including the bibliography and plot PDFs.
- All 48 original equation/align blocks and four proposition/proof blocks kept.
- All 22 original tables, 24 figures and three detailed algorithms kept.
- All 51 originally cited reference keys retained with their source passages.
- No unmatched nontrivial original prose lines.

Only reference wrappers and whitespace are normalized for the protected-block
comparison. Measurements are not regenerated or rescaled. This check preserves
the existing evidence; it is not an independent validation of that evidence.

The existing bibliography metadata warnings for
`Krasowski2023ProvablySafe` and `Dong2020CloudManufacturing` remain unchanged.
They do not prevent compilation and have not been silently filled with guessed
publication fields. This restructuring does not claim journal acceptance or
replace a venue-specific submission/readiness review.
