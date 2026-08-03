# PDF build and QA record

Date: 2026-08-03 (Asia/Seoul)

## Build

```bash
tectonic paper/main.tex --outdir output/pdf --keep-logs --keep-intermediates
```

Primary submission artifact:

- `output/pdf/main.pdf`
- 6 pages, A4
- 133,564 bytes
- PDF 1.5

## Checks completed

- Tectonic compilation succeeds.
- All six pages were rasterized and visually inspected.
- Pages 5--6 were re-rendered after integrating the corrected Search-view and
  shuffled-actionable results; no overflow, overlap, or clipped text appears.
- The original Table 2/Table 3 overlap on page 3 was fixed by constraining
  Table 2 to the ACL column width.
- No unresolved citation markers, `??`, placeholder references, or undefined
  citations appear in extracted PDF text.
- The review build displays `Anonymous ACL submission`.
- Extracted text contains no local username, local filesystem path, email
  address, or personal GitHub handle.
- PDF metadata contains no custom metadata, JavaScript, forms, or encryption.

## Non-blocking compiler notes

Tectonic still reports overfull box warnings for the fixed-width artifact and
generation-budget tables. Visual inspection confirms that both tables remain
inside their columns and do not overlap neighboring content. Underfull box
warnings are ordinary two-column justification and bibliography wrapping.

## Recheck after manuscript edits

Any later change to `paper/main.tex`, `paper/refs.bib`, or the figure should be
followed by recompilation, six-page raster inspection, and the anonymity text
scan before submission.
