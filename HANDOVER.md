# CarbonMint gauge reader: handover

Read this first on a new laptop or device, then `README.md`. Last updated 2026-10-13 (commit after `18896ed`).
No secrets are in this file or in git. Where a secret is needed, this says where it lives.

## 1. What the project is

Rice fields run AWD irrigation (flood, let dry, flood again) to save water, cut methane and keep the soil healthy.
Each field has a float gauge: red stripes rise out of a black sleeve as the water rises, about 1 stripe per cm
(assumption, not confirmed by the client). A drone photographs every gauge daily, usually 2 shots per visit. The
client (CarbonMint) wants software that reads the stripe count from the photo. **Target: 70–80% of photos accepted
(confidence ≥ 0.7) with the right count.** The gauge design can't change.

## 2. Names (agreed with the user, keep them)

| Name used on site, app, reports | What it is | Internal name in the repo |
|---|---|---|
| **v0** | The client's current reader (`src/enhanced-detector.ts`) | `gauge/v0.py`, `data/v0_reads.csv` (**our rebuild from its written description**) |
| **Colour method** | The team's colour isolation + gauge memory + shot transfer method (carbonmint-testing repo). **Always call it "Colour method", ours. Never "friend's" or "teammate's" on any page.** | `methods/teammate/`, `scripts/run_teammate.py` (folder names kept, never shown) |
| **v1** | Our current reader: stripe-rhythm reader + trained confidence + client rules + colour-method locator fallback | **`v2`** everywhere in files: `data/photo_reads_v2.csv`, `data/v2_reads.csv`, `models/v2_confidence.json`, comparison key `**v2**` |
| (not shown publicly) | Earlier draft, 72.4% | `v1` in files: `data/photo_reads.csv` (frozen), `data/v1_reads.csv`, `models/v1_confidence.json` |
| **Image V1** | The team's 5-test voting system (separate repo, separate report) | jayaprakash-pixel/carbonmint-testing |

## 3. Results (all on the 127 pilot photos; the client sent 128, team index 93 is missing from our copy)

**Our metric (headline):** accepted AND **exact** count, all 127 photos, confidence scored leave-one-field-out.

| Method | Accepted & exact | Accepted but wrong |
|---|---|---|
| v0 (rebuild) | 19 = 15.0% | 28 |
| Colour method | 51 = 40.2% | — |
| v1 (current) | **97 = 76.4%** | 16 |

- Under the **looser rule** used by Image V1 (±1, or ±3 on estimated tall stems, 9 uncountable photos left out, the team's
  recounted key `data/team_key_recounted.csv`): **v1 = 94/118 = 79.7%**, v0 21/118. The jump 76.4 → 79.7 is mostly from
  leaving out the 9 uncountable photos (93/118 = 78.8% exact on the same 118), not from the tolerance.
- **Image V1 head to head** (its per-photo `results/matrix.csv`): exact on our key 61/127 with 46 wrong accepts;
  its own rule 92/118 (78.0%, 10 wrong). It accepts counts that are 1–3 stripes off because its agreement rule is
  "within 15%".
- **Honest limits:** all figures are on the development photos (rules were designed on them); a fresh batch is the
  real test. 1 stripe = 1 cm unconfirmed. Dry gauge reads "Drying" (−10 cm) by v0's own rule, never "Irrigate now".
- Remaining v1 misses: one stripe short/extra at the sleeve or cap (7), leaves hiding the top (2), blurred short stems
  accepted with high confidence (4), washed-out far shots 24→13 (2), tiny red patch on a dry gauge (1). 7 of 16 wrong
  accepts are from field GAN-CP-3116-8972.

## 4. How v1 reads a photo (details in `docs/report/v1-service-report.pdf` section 4)

1. Find the rod: a stack of ≥ 3 separate red stripes on a near-upright line (red judged against green/blue, so shade
   counts); else a plain blue-grey rod; else the colour method's locator (needs OpenCV).
2. Straighten it, read the stripe rhythm: pitch = **shortest** autocorrelation lag ≥ 0.75 × the strongest; count **gap
   by gap** against the local pitch; faint end bands (< 0.3 × median) dropped; < 4 paint rows = dry (0).
3. Confidence: logistic model on 10 inputs (incl. whether the visit's other shot agrees) → P(count exact). Accept at 0.7.
4. Bad-gauge check (> 25 stripes or spacing that doesn't fit the rod width) → never accepted.
5. Visit reading = mean of accepted shots.

**Tried and dropped** (each scored the same way): Lanczos upscaling, extra stripe at the sleeve, rhythm extension,
extra confidence inputs, colour-method count/score as votes, **Upscayl** (below).

## 5. What is deployed and where

| Thing | Where | Notes |
|---|---|---|
| GitHub (private) | `SinghaniaAbhishekWNA/carbonmint-gauge` | Push with `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push` |
| Public site | https://carbonmint-gauge.vercel.app | Vercel project `carbonmint-gauge`; deploy `vercel --prod --yes` from repo root |
| Demo app (PIN sign-in) | https://carbonmint-gauge-app.vercel.app | Hosted lane: photos shrunk to 2048 px, no corrections stored |
| Local app | http://127.0.0.1:6900 | PM2 process `carbonmint-app`, entry in `C:\White Noise Project\ecosystem.config.js`; PM2 commands need an **Administrator** terminal; restart after Python changes |
| Phasedoc cockpit | http://127.0.0.1:6795 | PM2 `phasedoc-carbonmint`; files in the vault `White Noise/01 Projects/CarbonMint/Docs/phasedoc/` (not in this repo); change tasks only via `plan.py` (`plan.cmd` sets the env); phases P0–P9 done/partial, see `buildplan-mirror.md` |
| Docker service | `service/` | `cd service && GIT_COMMIT=$(git rev-parse --short HEAD) docker compose up -d --build`; drop a zip in `service/in`, report in `service/out` |
| Tour video | `public/media/explainer.mp4` (90 s) | Source project `videos/v1-story/` (HyperFrames, gitignored, Kokoro voice) |

**PINs / secrets:** in `C:\White Noise Project\CarbonMint\.env` (gitignored, never commit). Names are in `.env.example`
(`CM_ADMIN_PIN`, `CM_USER_PIN`, `CM_SECRET`, `CM_CLOUD`, `CM_MAX_UPLOAD`). Vercel has them as encrypted production env.
On a new laptop: copy `.env` across by hand (USB / password manager), or create new PINs and update Vercel
(`vercel env add CM_ADMIN_PIN production` etc.), then redeploy. The user's demo PINs were shared in the chat; consider
rotating them.

## 6. Data: what is and isn't in git

| In git | Not in git (copy by hand) |
|---|---|
| `data/labels.csv` (answer key, human spot-checked: round 1 10/15, round 2 15/15), all `*_reads.csv`, `data/comparison.json`, `data/gallery.json` | `way points/`: the 127 original drone photos (714 MB, contain field GPS). **Required to re-run anything.** |
| `media_private/photos/`: 1200 px copies, metadata stripped, served only after sign-in | `data/index.csv` (holds GPS) |
| `data/team_key_recounted.csv` (team's recounted key) | `.env` (PINs, secret) |
| | `third_party/upscayl/` (Upscayl engine + model; re-download, see §8) |
| | `data/cache/upscayl/`: Upscayl-upscaled crops (local only; were briefly in git in commit `18896ed`, removed in `a0a411f`) |
| `models/`, `docs/`, `service/`, `site/`, `public/` | `client-v0/` (client's private v0 source, see §9), `videos/`, `team-report/` |

## 7. Set up a new laptop

1. `gh auth login`, then `git clone https://github.com/SinghaniaAbhishekWNA/carbonmint-gauge.git` into
   `C:\White Noise Project\CarbonMint`.
2. Copy `way points/` and `.env` in by hand.
3. Python 3.11: `pip install -r requirements.txt opencv-python-headless==4.10.0.84 jsonschema==4.23.0`.
4. Check: `python -m unittest tests/test_gauge.py tests/test_app.py` (35 tests) and
   `python -m unittest discover -s service/tests` (8 tests).
5. Reproduce the numbers: `python -m gauge.run` (→ `data/photo_reads_v2.csv`), then `python scripts/compare.py`
   (→ `docs/comparison.md`, must show v1 = 97/127).
6. Optional: Docker Desktop (WSL2) for the service; Node + Chrome for `scripts/site_walk.mjs`; Vercel CLI for deploys;
   PM2 (as a Windows service, see the user's global setup) for the local lane.

## 8. Upscayl test (latest work, 2026-10-13)

Pre-registered in `docs/upscale_check.md` (rules committed before any run, commit `5cb0465`). Engine `upscayl-bin`
release `20251207-174704`, model `upscayl-standard-4x` (hashes in the doc). **Licence AGPL-3.0**: shipping it in the
client's container would need source-sharing; only tested so far.

- **Test A (what would ship): failed the gate, not adopted.** Triggers (no rod, half-width < 14 px, pitch < 16 px) hit
  10 photos; v1 was already right on 9. Result 97 → 97, wrong accepts 16 → **17** (a far shot read 23 correctly but in
  review became an accepted 22). Upscayl also invented 7 stripes on a dry gauge (blocked by the other-shot rule).
  `UPSCALE` stays off; v1 unchanged.
- **Test B (every photo) + safety checks S1/S2: not completed.** Stopped by the user at 52/127 crops (laptop
  overheating; ~15–20 s per crop on Intel Iris Xe, ~2 GB RAM). No result claimed. To resume on a stronger machine:
  download the engine + model into `third_party/upscayl/` (`bin/upscayl-bin.exe`, `models/upscayl-standard-4x.{param,bin}`,
  check the hashes in the doc), then `python scripts/upscale_eval.py upscale` (reuses any cached crops in `data/cache/upscayl/`), then
  `python scripts/upscale_eval.py score`.
- The team's Image V1 has its own upscaling (FSRCNN ×2 retry when < 3 of 5 tests agree). After the team tightened the
  retry rule it changes **0 of 128** photos (their `docs/upscale_check.md`, `results/matrix.csv`).

## 9. The client's real v0 code (just received, not yet used)

Downloaded 2026-10-13 from the client's private repo `Carbon-Mint/reactml`, branch `agrios-st1`, commit `f348b747f`,
folder `packages/water-level-processor` (61 files; detector in `src/enhanced-detector.ts`, 651 lines). Kept in
`client-v0/` (gitignored, client's private code). **Nothing run yet; the user will say what to do with it.** Likely
next step: compare it with our rebuild `gauge/v0.py` and re-score v0 with the real code (our v0 numbers assume the
written description; 4 values were marked ASSUMED). Re-download:
`git clone --filter=blob:none --no-checkout --branch agrios-st1 --single-branch https://github.com/Carbon-Mint/reactml.git`
then `git sparse-checkout set packages/water-level-processor && git checkout agrios-st1` (needs access to the org).

## 10. Reports for stakeholders

| File | What |
|---|---|
| `docs/report/v1-service-report.pdf` | Our technical report (13 pages): spec, architecture, interface contract, algorithm with exact rules, evaluation method, results, failure analysis, performance, backlog, handover checklist (8/12) |
| `docs/report/v1-loose-rule-report.pdf` | Companion note explaining the 79.7% figure |
| `image v1 - service report (White Noise).pdf` (repo root, gitignored) | The team's Image V1 report, technical edition we wrote from their code (13 pages); source `team-report/` |
| `scripts/letterhead.py` | Stamps the White Noise letterhead (logo `docs/report/wn-logo.png`) on any PDF |

Reports are HTML printed with headless Chrome (`--print-to-pdf --no-pdf-header-footer`), then stamped.

## 11. How the user likes to work (keep doing this)

- **Honest numbers only.** Pre-register rules before a scored run; report results whichever way they go; label
  development-set results as such; never tick or claim what wasn't verified.
- **Strict exact metric is the headline** (76.4%); the looser figure only with its rule stated.
- Public pages: no phasedoc text, no "friend/teammate" wording; the colour method counts as ours.
- Secrets never in git or printed (except when the user asks for their own PIN).
- PM2 for every local service; restart needs an elevated terminal (UAC prompt the user must accept).
- Plain, short updates; confirm before outward actions the user didn't ask for.

## 12. Open items

1. Use the client's real v0 code (§9): waiting for the user's instruction.
2. Fresh, unseen labelled photo batch: the most important validation step.
3. Confirm cm per stripe and the dry-gauge soil-state rule with the client.
4. Person to review the 16 accepted-but-wrong v1 photos.
5. Upscayl Test B: resume only on a stronger machine (§8).
6. Phasedoc: P5.1.3 (company benchmark), P6.1.4 (cm calibration), P2.1.2 (trained detector), P8.1.6 (90%) open.

## 13. Continue this conversation

- Same laptop: `claude --resume 0bee14f0-d774-44fb-8be2-b332113e7a48` from `C:\White Noise Project\CarbonMint`.
- Any device: https://claude.ai/code/session_01Unw2Jx87HwyXhwYjqPT78Y
- New session elsewhere: open the repo and say "read HANDOVER.md and continue".
