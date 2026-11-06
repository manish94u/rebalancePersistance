# Repository Export Validation

Date: 6 November 2026.

This records verification of the repository export, not a new scientific
experiment or a rerun of the historical cloud trials.

## Verified

- 160 imported research files match their recorded source or documented
  packaging-fix digest. The original research workspace was not edited.
- All 48 manifest-covered reviewer evidence files pass their original hashes.
- The frozen checkpoint and numerical episode records are unchanged.
- Four archived analysis tests and eleven publication/simulator tests pass.
- The standard simulator smoke run completes for three scenarios, twelve
  variants, twenty intervals, and one seed.
- The tiered runner completes a two-interval, one-seed smoke run across twelve
  variants with 20,000 subscriptions. This is a plumbing check, not new paper
  performance evidence.
- A fresh temporary-copy build produces the main paper at 25 pages and the
  appendix at 53 pages, without unresolved references or overfull-box failures.
- Manuscript preservation retains 48 equation/align blocks, four proof-related
  blocks, 22 tables, 24 figures, three detailed algorithms, and 51 citation keys.
- Text and PDF metadata were checked for the configured private-path,
  infrastructure-identifier, endpoint, and credential patterns. The extracted
  text/metadata check covered 43 PDF files, including duplicated figure assets.
- The source/ZIP boundary scan passes. It is a targeted check, not a guarantee
  from a full commercial secret-scanning product.

## Packaging-Only Corrections

1. The legacy tiered setup table now closes with `table`, matching its opening
   environment, instead of `table*`. A regression test covers the correction.
2. The submission build forces each `latexmk` pass with `-g` so references to
   the other PDF resolve even when the checkout initially has no auxiliary files.

Both original and exported digests are recorded in
`provenance/import-manifest.json`. Neither correction changes a measurement,
formula, learned weight, policy decision, or figure value.

## Preserved Warnings and Access Boundary

The existing BibTeX warnings for incomplete metadata in
`Krasowski2023ProvablySafe` and `Dong2020CloudManufacturing` remain.
No publication fields were invented to suppress them.

Private cloud client/server source, credentials, raw event payloads, resource
identifiers, and internal logs are not part of this release. Cloud replication
requires a separately authorized implementation and environment. The supplied
CI workflow covers offline checks only; its remote execution status is separate
from the local checks reported here.
