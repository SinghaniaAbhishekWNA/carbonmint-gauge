# Upscayl in v1: pre-registered test

Written and committed **before** any scored run. The rules below are not changed after seeing the results. If one ever is, the earlier result is reported too.

## Engine and model (fixed)

| Part | Value |
|---|---|
| Engine | `upscayl-bin` from github.com/upscayl/upscayl-ncnn, release `20251207-174704`, Windows build |
| Engine binary | `upscayl-bin.exe`, SHA-256 `294d31be8f29d047c0d91a8dcd5e739616ece56bce3188ac688f9a52d70abe60` |
| Model | `upscayl-standard-4x` (Upscayl's default), from github.com/upscayl/upscayl v2.15.0 `resources/models` |
| Model files | `.param` SHA-256 `35330ececcea33b6c397a72548e788d5d53becee4734c50b7fada36e89f10a86`; `.bin` SHA-256 `713ee713b0353afaa27976f0563a64a5043bd70b9bd8936c2e26e25ebcdbcddf` |
| Scale | ×4 |
| Hardware | Intel Iris Xe (Vulkan) on the laptop in the service report |
| Licence | The Upscayl app and `upscayl-bin` are AGPL-3.0. Fine for testing. Shipping it in the client's container means offering its source; that is a decision for later. |

Only this one model is tested. No other model is tried after seeing results.

## Baseline (v1 today, nothing changed)

Leave one field out, exact count, all 127 photos (`data/labels.csv`):
- 97 accepted and exact (76.4%)
- 16 accepted but wrong
- 14 review
- 0 no gauge

Looser rule (±1, or ±3 on estimated tall stems; 118 countable): 94 (79.7%).

127 photos: the client's batch has 128, and one photo (team index 93) was never in our copy.

## The crop

Around the rod v1 found:
- along the rod, from `t0 − (0.6·L + 80)` to `t1 + (0.5·L + 150)`, which is the same stretch the reader samples
- across, ±(4 · half-width + 32) px
- clipped to the photo

With no rod, the crop is the colour-method locator's box with half its width and a quarter of its height added as margin. With no box either, there is no crop. The crop is upscaled ×4, and v1's own finder and reader are run on it. Box and lengths are divided by 4 to map back to the photo.

## Test A: pipeline (what would ship)

**Triggers**, decided from the normal v1 read before any upscaling:
1. No rod found (step 1, find the rod), or
2. Rod half-width under 14 px (step 1: the gauge is tiny in the picture), or
3. Stripe gap under 16 px (step 2: stripes too fine to read well).

**Adoption rules**, applied in this order:

| Rule | What it says | v1 step |
|---|---|---|
| R1 | The upscaled read must find a rod and give a count; otherwise keep the original. | — |
| R2 (dry guard) | If the original reading is 0 and the upscaled one is above 0, adopt only if the visit's other shot (original reading) is above 0. | Step 4, grey rod = dry |
| R3 (other shot) | If the visit's other shot has a reading, adopt the upscaled count only if it is within 1 of that reading. If there is no other reading, adopt it. | Step 3, the other shot |
| R4 | If adopted, the photo's row is the upscaled read (geometry mapped back) with `upscaled = 1`; otherwise the original row with `upscaled = 0`. | — |

The "other shot" in R2 and R3 always means its **original** reading, so the order of shots never matters.

**Confidence:** the leave-one-field-out model is retrained on these rows with one extra input, `upscaled` (0/1). The input is always included; it is not added or dropped after seeing results.

## Test B: stress test (every photo)

Same crop, same R1–R4 and the same confidence retraining, but every photo with a rod or a locator box is upscaled. This answers whether Upscayl helps v1 anywhere at all. It is evidence, not a candidate to ship (too slow: about 1–2 hours on this laptop).

## Safety checks

- **S1, invented stripes.**
  - For every photo whose hand count is 0 (29 dry gauges), the upscaled crop must read 0. Any stripe on a dry gauge counts as invented.
  - Also, the plain grey cap above the first stripe of every accepted-and-exact photo with a cap at least 1.5 stripe gaps long, upscaled on its own, must contain no stripe peaks.
- **S2, shrink and restore.** Take every photo that v1 has accepted and exact with a half-width of 25 px or more. Shrink the crop to a quarter (area-average), then upscale ×4 with Upscayl, and separately with Lanczos. Report how often the count comes back exact, for each.

## Gate (decided now)

Upscaling is turned on in v1 only if **Test A** gives all of these:
- accepted and exact above 97, or equal with fewer accepted-but-wrong
- accepted-but-wrong at most 16
- S1 finds 0 invented stripes
- the extra time on the 127 photos is at most 50% of the 236 s reading time

Otherwise it stays off (`UPSCALE=off`, the default), and the result is reported as tried and not adopted.

## Results

(Filled in after the runs. Every triggered photo is listed with before/after, hand count, accepted before/after, adopted or blocked and why.)
