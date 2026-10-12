# How accuracy is measured

The company's own accuracy definition is **still unknown**. Until they share it, every result is reported four ways, so
it can be compared with any definition they use.

## The reading

- A reading is the number of red rings showing above the sleeve. Rings hidden by leaves still count, because the
  water level doesn't change when a leaf covers a ring.
- A ring cut by the sleeve edge counts as 1 if more than half of it shows, otherwise 0. Readings are whole rings (rule set 2026-10-11).
- The unit is rings. The ring-to-centimetre scale and zero point are still to come from the company (phasedoc P6.1.4).

## Four numbers

| Name | Meaning |
|---|---|
| Exact, per photo | The reading for one photo matches the label (within half a ring). |
| Within 1 ring, per photo | The reading for one photo is at most 1 ring away from the label. |
| Exact, per visit | The fused reading for a visit (usually 2 shots) matches the visit label. |
| Within 1 ring, per visit | The fused reading for a visit is at most 1 ring away. **This is the headline number for the 80% target.** |

- A visit's label is the median of its photos' labels. If two shots differ, that is the mean of the two.
- A photo where no rod is found counts as a **miss**. It is never dropped from the count.

## Labels

- There are no human labels yet. `data/labels.csv` holds Claude-read **silver** labels, read by eye from straightened,
  enlarged rod strips with a pixel ruler.
- 24 of the 127 photos are marked low-confidence (blurred, far, or with the sleeve hidden).
- Before any accuracy is claimed outside the team, a person checks 15 seeded-random labels (`python -m gauge.spotcheck`,
  about 5 minutes). If fewer than 14 of the 15 agree, the labels are redone first.

## Review-queue rule

- A visit is **auto-accepted** only when two conditions hold:
  - its confidence is at or above the threshold
  - it has no flag: shots disagree by more than 1 ring, no rod found, or a one-day timeline spike
- Everything else goes to a person on the review page (`python -m gauge.app`).
- The threshold is fitted on training plots only. In leave-one-plot-out evaluation each held-out plot uses a threshold
  chosen without it.
- The eval prints the review share next to the accuracy, because a low review share and a high accuracy have to hold
  at the same time.

## Leave-one-plot-out

- There are 7 plots. Each fold holds one plot out, fits the review threshold on the other 6, and scores the held-out
  plot.
- The reader itself has no learned weights. Its rules were written while looking at all 7 plots, so the numbers are
  optimistic until the spot-check and a fresh batch of visits confirm them.
