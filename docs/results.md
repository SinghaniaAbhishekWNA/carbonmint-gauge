# Results

<!-- baseline -->
## Baseline: plain ring counter

Counts ring bands that cover at least 70% of the rod width (what a quick counting script does). Same photos, same silver labels.

| Level | n | Exact | Within 1 ring |
|---|---|---|---|
| Photo | 127 | 42.5% | 63.0% |
| Visit (two shots fused) | 66 | 40.9% | 63.6% |
<!-- /baseline -->

<!-- full -->
## Full pipeline (measure, fuse, timeline, review rule), leave-one-plot-out

Only the review threshold is fitted, on the six training plots of each fold. Labels are Claude-read and were checked by a person in two seeded rounds of 15 (round 1: 10/15 exact, so labels were fixed and switched to whole rings; round 2: 15/15). The reader's rules were written while looking at all seven plots, so a fresh batch of visits is still the real test.

| Level | n | Exact | Within 1 ring |
|---|---|---|---|
| Photo | 127 | 70.9% | 87.4% |
| Photo, clear labels only | 103 | 76.7% | 95.1% |
| Visit (all) | 66 | 69.7% | 92.4% |
| Visit, auto-accepted | 57 | 73.7% | 94.7% |

Review share: 9/66 visits (13.6%) go to a person.

### Per held-out plot

| Plot | Threshold | Visits | Exact | Within 1 | Auto-accepted | Auto within 1 |
|---|---|---|---|---|---|---|
| AIT-CP-2050-9573 | 0.0 | 10 | 50.0% | 90.0% | 9 | 88.9% |
| AIT-CP-5286-2931 | 0.0 | 9 | 77.8% | 100.0% | 8 | 100.0% |
| GAN-CP-2670-3131 | 0.0 | 10 | 60.0% | 100.0% | 8 | 100.0% |
| GAN-CP-3116-8972 | 0.0 | 9 | 66.7% | 66.7% | 7 | 71.4% |
| GAN-CP-3158-8831 | 0.0 | 9 | 55.6% | 88.9% | 6 | 100.0% |
| GAN-CP-4035-3848 | 0.0 | 10 | 80.0% | 100.0% | 10 | 100.0% |
| GAN-CP-5152-3075 | 0.0 | 9 | 100.0% | 100.0% | 9 | 100.0% |

### Misses (visit off by more than 1 ring)

| Plot | Date | Label | Read | Confidence | Flags | Crops |
|---|---|---|---|---|---|---|
| AIT-CP-2050-9573 | 2026-10-06 | 22.0 | 19.0 | 0.54 | - | `data/crops/dji_fly_20261006_095802_0473_1791266309994_photo.jpg`, `data/crops/dji_fly_20261006_095804_0474_1791266311161_photo.jpg` |
| GAN-CP-3116-8972 | 2026-09-26 | 6.0 | 3.0 | 0.5 | - | `data/crops/dji_fly_20260926_103920_0312_1790423004530_photo.jpg`, `data/crops/dji_fly_20260926_103946_0313_1790423006484_photo.jpg` |
| GAN-CP-3116-8972 | 2026-09-27 | 24.0 | 12.0 | 0.38 | timeline spike | `data/crops/dji_fly_20260927_101916_0333_1790503250613_photo.jpg`, `data/crops/dji_fly_20260927_101934_0334_1790503253321_photo.jpg` |
| GAN-CP-3116-8972 | 2026-10-01 | 4.0 | 0.0 | 0.6 | - | `data/crops/dji_fly_20261001_101206_0355_1790917165728_photo.jpg`, `data/crops/dji_fly_20261001_101230_0356_1790917163816_photo.jpg` |
| GAN-CP-3158-8831 | 2026-09-27 | 23.0 | 21.0 | 0.65 | shots disagree | `data/crops/dji_fly_20260927_102948_0343_1790503269113_photo.jpg`, `data/crops/dji_fly_20260927_102958_0344_1790503270810_photo.jpg` |
<!-- /full -->
