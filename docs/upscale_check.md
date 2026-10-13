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

Run on 2026-10-13. Rules above unchanged.

### Test A: pipeline. Gate **failed**, so upscaling stays off.

| | Baseline | Test A |
|---|---|---|
| Accepted and exact (127) | 97 = 76.4% | **97 = 76.4%** |
| Accepted but wrong | 16 | **17** |
| Review / no gauge | 14 / 0 | 13 / 0 |
| Looser rule (118) | 94 | 94 |

| Photo | Trigger | Before | Upscayl read | After | Hand count | Other shot | Accepted before → after | Decision |
|---|---|---|---|---|---|---|---|---|
| 3158, 27 Sep `_0343` | thin rod | 23 | 22 | 22 | 23 | 22 | no → **yes** | adopted (R3, matches other shot): a right reading in review became a confident wrong one |
| 3116, 5 Oct `_0457` | thin rod | 2 | **7** | 2 | 0 | 0 | yes → yes | blocked by R3. Upscayl turned a small red patch into 7 stripes. |
| 3116, 6 Oct `_0484` | no rod (colour locator) | 0 | no rod found | 0 | 0 | 0 | yes → yes | R1: no reading on the upscaled crop |
| 7 more dry gauges and one no-rod photo | thin rod / no rod | 0 | 0 | 0 | 0 | 0 | yes → yes | adopted, no change |

**Why it does not help:**
- The pre-registered triggers fire only where the gauge is tiny in the picture (10 photos). v1 was already right on 9 of them.
- On the one it got wrong, Upscayl made things worse by inventing stripes.
- v1's real misses (blurred short stems, washed-out far shots, leaves hiding the top) have normal-size gauges, so the triggers do not fire on them.

The gate needed accepted-but-wrong ≤ 16; it is 17. Upscaling is **not adopted**; `UPSCALE` stays off and nothing in v1 changed.

**Run time:** about 15–20 s per crop on the Intel Iris Xe. A typical 0.44-megapixel gauge crop took 60–150 s, and the engine used about 2 GB of memory.

### Test B: every photo. Upscaling makes v1 **worse**.
Resumed on 2026-10-13 and completed (127 gauge crops, about 70 min on the Intel Iris Xe). Same rules R1–R4.

| | Baseline | Test B |
|---|---|---|
| Accepted and exact (127) | 97 = 76.4% | **82 = 64.6%** |
| Accepted but wrong | 16 | **21** |
| Review / no gauge | 14 / 0 | 24 / 0 |
| Looser rule (118) | 94 | 84 |

**What Upscayl did to the counts:**
- Its reading differs from v1's original on **53 of 127** photos.
- In **41** of those, v1 was right and Upscayl's reading is wrong.
- In **0**, v1 was wrong and Upscayl's reading is right.
- Rule R3 (must agree with the other shot) blocked 46 of the 53. The 8 that got through all made the reading worse, or left a wrong reading wrong:

| Photo | Before | After | Hand count | Accepted before → after |
|---|---|---|---|---|
| `_0338` | 3 | 4 | 3 | yes → no |
| `_0422` | 22 | 23 | 22 | yes → no |
| `_0343` | 23 | 22 | 23 | no → yes (now a confident wrong reading) |
| `_0346` | 25 | 14 | 23 | yes → no |
| `_0401` | 18 | 17 | 18 | yes → no |
| `_0471` | 3 | 2 | 3 | yes → yes (now wrong) |
| PK 23 Sep | 25 | 21 | 25 | yes → yes (now wrong) |
| `_0305` | 9 | 10 | 9 | yes → no |

**Confidence:** 72 photos kept the same count but now carry the upscaled read's signals (sharpness, pattern strength). With those, 11 correct photos fell below 0.7 and 5 rose above it (2 of them correct).

**Why:** Upscayl's model is trained to make photos look sharp, not to keep stripe positions. On gauge crops it shifts, merges or adds stripe edges, so the rhythm v1 measures changes. S2 confirms this directly.

### S1: invented stripes. **Failed** (1 of 29 dry gauges)
- Dry gauges: Upscayl's crop of `_0457` (hand count 0) reads **7 stripes**. On the other 28 dry gauges it reads 0.
- Stripe-free caps: 1 of 67 upscaled caps shows a stripe-like band, and the same cap shows one after plain Lanczos enlarging too. That band is real paint at the cap edge, not something Upscayl invented.

### S2: shrink and restore. Upscayl is **worse than plain Lanczos**.
81 accepted-and-exact photos (half-width ≥ 25 px), shrunk to a quarter, then enlarged ×4:
- Lanczos gives the exact count back on **77/81** (95%).
- Upscayl gives the exact count back on **69/81** (85%).

### Conclusion
On these photos Upscayl does not raise v1's accuracy anywhere:
- **Test A** (only where the gauge is tiny): 97 → 97, with one more confident mistake.
- **Test B** (every photo): 97 → 82.
- It changes correct counts far more often than it fixes wrong ones (41 against 0), and it invented stripes on one dry gauge.

**Upscaling is not adopted.** `UPSCALE` stays off and v1 is unchanged. If far-away photos arrive in a future batch, a non-generative enlarger (Lanczos, or FSRCNN as the team found) is the safer candidate.

**Bug found and fixed on the way:** on some upscaled crops, v1's `pitch()` crashed when every autocorrelation peak was negative (no rhythm). It now falls back to the strongest peak. v1's readings on the 127 real photos are unchanged (checked), and a test reproduces the old crash.

Raw results: `data/upscale_eval.json`. Upscaled images: `data/cache/upscayl/` (local only, not in git).
