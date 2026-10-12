# Teammate method (vendored, unchanged)

Source: github.com/jayaprakash-pixel/carbonmint-testing, commit 7d32b19 (2026-10-10), `pipeline/` copied as is.
Their best locator is "method 3 final": brightness-normalised colour isolation, then sibling transfer within a visit
(SIFT + RANSAC), then Gauge memory for visits where neither shot is confident; rings by `pipeline/rings.py`.

`sorted/` holds hard links to our photos in the layout their code expects (not committed). Their photo #93 is not in
our photo folder, so that row is dropped (127 photos). Run: `python scripts/run_teammate.py`.
