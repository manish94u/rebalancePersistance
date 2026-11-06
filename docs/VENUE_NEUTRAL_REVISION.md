# Venue-Neutral Repository Edition

The repository no longer presents the manuscript as targeting a particular
journal. The full reference files use `Rebalancing-Connection-Reference` names,
and all three documents use the template's `nonacm` manuscript mode without a
journal selector or a venue-specific self-citation block. The underlying
single-column manuscript layout is retained.

The README and build/preservation tools use generic wording and filenames.
Two evidence schema identifiers are now descriptive of the experiment rather
than a venue, and two development protocols no longer carry a `venue_target`
field. These are publication metadata changes, not new experiments.

## Preservation Checks

- All fields other than the four explicitly declared metadata fields match
  the preceding repository edition. Their canonical payload digests are in
  `provenance/venue-neutral-check.json` and are regression-tested.
- Model weights, CSV measurements, confidence intervals, experimental settings,
  body prose, equations, tables, and plotted data are unchanged.
- Evidence manifests and the two reviewer ZIPs are synchronized to this
  metadata-only edition. Previous source hashes are retained in provenance.
- Journal names in genuine bibliography entries and upstream template code
  remain unchanged. They identify cited publications or template support and
  are not statements of this manuscript's submission destination.
- The original research workspace outside this Git checkout is untouched.

Git history retains the earlier edition for auditability. This revision does
not rewrite history or delete the original measured records.

## Validation

All 18 offline tests pass. The rebuilt main paper, appendix, and full reference
remain 25, 53, and 72 pages respectively. Both submission documents also pass
the desktop editor compiler. Their rendered pages pass the boundary and
unresolved-reference checks; the revised front matter was visually inspected.
