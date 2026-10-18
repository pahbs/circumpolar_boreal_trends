# ATL03 v007 reclassification: decisions and results log

**Summary slides for collaborators:** [Google Slides deck](https://docs.google.com/presentation/d/1L1QN_-S83ehHG6zJWZfWqqmeBviaDbzCudrvp0YADe0/edit) (deck version 1, 15 Oct 2026, config v0.1). Source outline `docs/slides/outline.md`; figures `docs/figures/`. Update the deck with every significant change to methods or results.

**Newest entries at the top.** Each entry: what was decided or found, why, and what it changes. Methods as implemented:
`atl03_reclassification_methods.md`; plan: `atl03_reclassification_plan.md`. Terms as defined in both.

**Standing rule (14 Oct 2026, Paul Montesano):** the goal is to run this approach on **all circumpolar tiles for every year**.
Development uses interior Alaska, the Kenai and the Seward Peninsula, so every decision must be checked against overfitting to
those areas (methods §7): physical or instrument-based thresholds only, no inputs that exist only in Alaska, settings chosen by
leave-one-region-out, out-of-region results reported, and wider validation (LVIS 2017/2019 in Canada and Alaska, Fennoscandian
ALS, Eurasian data) before scale-out.

## Current status and next steps

**Status (18 Oct 2026): v0.6 is the final version of this series; for the training pool it is a trade-off** (entries
18 Oct, "Training pool"). **All observations**, CanElevation (independent discrete-return lidar), same segments, today →
v0.6: false shrubs over bare ground 14 → 4 %, short-vegetation bias +1.0 → +0.3 m, 20 m+ forest −4.7 → −2.9 m, r² 0.73 → 0.77,
forest called bare 1 → 5 %, coverage 94 → 51 % (acceptable). **Training pool (strong beams, solar elevation < 5°):** today is
already good (CanElevation r² 0.86, false shrubs 6 %); v0.6 removes most false shrubs (CanElevation 6 → 2 %, G-LiHT 37 → 15 %,
Seward 25 → 6 %), keeps 74–84 % of today's heights, but reads forest ≥ 10 m about 1 m shorter (CanElevation −1.7 → −2.7 m,
G-LiHT −1.8 → −2.8 m) and writes 3–8 % of forest as 0 m: it fails the tall-forest rule for this cohort. **v0.6 is the better
input over tundra and shrubland; for the forest part of the night / low-sun pool it is not yet better than today.**
LVIS counts for less. All notebooks (00–11), methods, deck and figures describe v0.6.

**Open issues:**
0. **Training pool, forest:** keep more night canopy photons (v0.6 labels 19 % of night strong-beam canopy photons as
   noise, ATL08 11 %) and stop zeros over forest; or use v0.6 only to remove false heights over short vegetation.
1. Tall forest still 2–3 m short against canopy-height-model lidar; the ground sits > 1 m too high under a fifth to a third
   of 15 m+ segments in every version (dense canopy, ≤ 2 ground photons per 10 m bin).
2. Rare implausible heights over tundra (one segment at 38 m over < 2 m Seward tundra; LVIS 0–1 m non-zero heights +9 m):
   add a plausibility cap before production.
3. Reference metric: footprint-level vs segment RH98 (40 % of G-LiHT "false vegetation" has trees in some footprints).
4. Wider validation before scale-out (NEON, Nordic ALS); canopy cover on hold.

**Earlier status (17 Oct 2026, 21:45):** v0.5 results mixed (short vegetation better, tall forest ~0.5 m shorter on CanElevation).

**Earlier status (17 Oct 2026):** v0.4 built and validated on independent data; not adopted for training (r² on LVIS fell
0.51 → 0.46, coverage 51–52 %).

## Versions at a glance (newest first): the central idea of each version

Each version changes **one idea**, chosen from the largest error left by the previous version. Full rule definitions:
methods §8; evidence: the dated entries below.

| Version | Central idea (why it was made) | What changed | Result | Status |
|---|---|---|---|---|
| **v0.6** (18 Oct) | **v0.5's ground, without losing sparse ground under dense canopy.** v0.5 raised the ground > 1 m in 8–15 % of CanElevation segments ≥ 10 m. | `ground.dense_min_photons` 3 → 1 (fraction test only). | CanElevation r² 0.770 (v0.4 0.775, v0.5 0.760), false vegetation 4.4 %, 20 m+ −2.93 m (v0.4 −2.67, v0.5 −3.29); G-LiHT r² 0.575; Seward bias 0.0 m. Training pool (strong, sun < 5°): false shrubs removed, forest ≥ 10 m ~1 m shorter than today. | **final of this series; trade-off for the training pool** |
| v0.5 (17 Oct) | **Put the ground where the photons are.** In v0.4's false heights over bare ground (G-LiHT ALS < 1 m, v0.4 > 0 m) the ground was > 1 m off in 30 % and ground photons were called canopy in 25 %; photons below the surface (after-pulses under bright or specular surfaces, daytime clusters) pulled the lower envelope down. | First ground guess per 10 m bin = lowest layer (2 × 0.6 m) with ≥ half the densest layer's photons (`ground.start: lowest_dense_layer`), not the 5th percentile of signal photons. | Development sites (harness): r² 0.51 → 0.55, false vegetation 16 → 13 %, tall forest 0.1–0.2 m lower. Independent: short vegetation better everywhere, tall forest ~0.5 m shorter on CanElevation. | replaced by v0.6 |
| **v0.4** (17 Oct) | **Tell bare ground from vegetation correctly.** v0.3's short-vegetation gains came from writing 0 m, also over real forest; and on slopes the ground was found metres too low, so ground photons became "canopy". | (A) ground window widens with along-track slope (± 0.6 m + 5.5 m × slope); (B) one presence test on all photons above the ground (3σ over solar background) + "would a 25 %-cover canopy have been seen?" decide height / 0 m / NaN. Old 0 m rule removed. | Independent (LVIS + CanElevation): forest at 0 m 6.2 → 2.8 %, false vegetation 7.2 → 6.3 % (today 16 %), big gains on slopes; CanElevation best on every measure but coverage; LVIS r² 0.51 → 0.46 and RMSE up (heights of newly detected short vegetation unreliable); coverage 62–64 → 51–52 % (today 88–95 %). | tested; not adopted for training; leads to v0.5 |
| v0.3 (15–16 Oct) | **Stop solar noise from inventing tall canopy tops.** > 30 m "canopy" over tundra in bright daylight. | Canopy-top recovery needs 3σ over background; column-test top = plateau, not maximum. | LVIS: spurious vegetation 47 → 12 %, tall forest nearly unbiased. **But** short-vegetation gains were mostly zeros, and 6–12 % of forest ≥ 5 m was 0 m (16 Oct). | replaced by v0.4 |
| v0.2 (15 Oct) | **Keep sparse tall-canopy photons, and say "no data" instead of 0 m when the signal is too weak.** v0.1 lost tall-forest canopy and wrote 0 m for 61–66 % of segments. | Canopy column test; `low_signal` NaN flag; shots from segment length; track shifts only when they help. | Tall forest back to (and in most cells better than) today; short vegetation no better. | replaced by v0.3 |
| v0.1 (14 Oct) | **Rebuild ground and canopy labels from all ATL03 photons**, with instrument-based thresholds instead of ATL08's classes. ATL08 classes give spurious shrub heights and underestimate tall canopy. | Noise filter, iterative ground, canopy classes, short-vegetation guard. | Seward spurious vegetation 50 → 12 %; tall forest much worse (canopy photons lost). | replaced by v0.2 |

**Names used for the 30 m versions** (from 17 Oct; methods, Terms): **ATL08 · PhoREAL (today)** = NASA's ATL08 photon classes
binned by SlideRule PhoREAL, our training data today (formerly "current v7 30 m"); **ATL08 · our binning (control)** = the
same classes binned by our code, to separate binning from classification (formerly "check"); **reclassified v0.N** = our
photon classes, our binning (formerly "new"). Entries before 17 Oct use the former names.

**Earlier status (16 Oct 2026):** v0.3 short-vegetation gains are mostly zeros (entry 16 Oct, "Correction"); v0.4 = the 0 m rule.
**Earlier status (15 Oct 2026, night):** v0.2 committed (`c8efd09`) and in the deck. **v0.3 in progress**
(`config/atl03_reclass_v0.3.yaml`): noise-robust canopy top (diagnosed from impossible > 30 m tundra heights); independent
LVIS 2019 validation done (notebook 09: false vegetation 47 % → 12 %, tall forest nearly unbiased, coverage ~62 %);
CanElevation lidar 2019–2025 done (notebook 10: false vegetation 30 % → 9 %; night / weak-beam canopy now
underestimated, the next fix).
NEON needs an API token (Paul to create). Canopy cover on hold.

**v0.3 (proposed, in order):**
1. Short-vegetation overestimate (G-LiHT 0–1 m: +3.0 m; Seward 1–2 m: +2.3 m where reported): find which photons set RH98.
2. Coverage: 30 % of segments "not enough signal", most in day · weak beams (339 of 783 reported): check the 15-photon
   threshold against the ATL08 ATBD and against bias by signal.
3. Tall forest: close the remaining −2.4 to −4.1 m; check the Kenai 10–15 m failure and which reference percentile fits.
4. Overfitting check on the column-test settings (leave-one-region-out), then items 5–6 of v0.2 (slope × forest strata,
   LVIS) to widen validation.
5. Canopy cover: the method itself (ratios implausible even with reference photon labels).
6. Runner: one-run lock file (two runners overlapped on 15 Oct).

**v0.2 (in order):**
1. **Done (diagnosed).** Footprint matching is not the cause of r = 0.43 (shift scan, entry below); low r is daytime / weak-beam
   noise. 02: keep horizontal shifts only when they clearly help; 05: report by day/night × beam.
2. **Done (sample-tested).** Shots per segment from segment length (fixes `Ev`, `Eg`, cover, guard).
3. **Done (sample-tested).** `low_signal` flag with `h_canopy` = NaN; 0 m only with enough signal and canopy RH98 < 0.6 m.
4. **Done (sample-tested; per-region check pending).** Tall-forest canopy retention: canopy column test.
5. Validation strata: slope class × forest / non-forest (circumpolar layers), reported for every version.
6. Add gridded LVIS 2017/2019 (ABoVE_LVIS_VegetationStructure_1923) as a second airborne reference.
7. Rerun 01–08; compare v0.1 vs v0.2 per region, per height class, per slope × forest stratum. Expected ~4–5 h as before
   (notebook 02 ~3 h dominates); ~2–2.5 h if the Hansen lookup is cached and offsets run per tile in parallel.
8. **Done.** Figures: shared style (`lib/plot_style.py`), vegetation-height colormap, ESRI Light Gray basemap on maps.

**Then, before scale-out:** wider validation (NEON boreal/Arctic, Canadian provincial ALS, Fennoscandian national ALS).
---

## 2026-10-18 · Training pool (strong beams, sun < 5°): v0.6 removes false shrubs but shortens forest by ~1 m (Paul Montesano's question)

**Question:** the biomass training pool uses strong beams at night and with the sun < 5° (low-sun summer observations). What
does v0.6 do to that cohort? Notebook 11, section 6 (`runs/v0.6/cohort_summary.csv`, `cohort_dropped.csv`; figures
`11_cohort_*.png`): 12,969 cohort segments with a reference (9,554 night, 3,415 low sun); same segments for today, v0.4,
v0.5, v0.6; 95 % intervals from resampling whole tracks.

| cohort, today → v0.6 | CanElevation (32 tracks) | G-LiHT (48) | LVIS (77; low weight) | Seward drone (10) |
|---|---|---|---|---|
| today's heights dropped | 20 % | 26 % | 16 % | 7 % |
| false shrubs | 5.9 → 2.0 % | 37 → 15 % | 11 → 6 % | 25 → 6 % |
| bias < 2 m (m) | +0.84 → +0.07 | +3.3 → +1.3 | +2.2 → +0.8 | +1.1 → −0.2 |
| bias ≥ 10 m (m) | −1.66 → −2.72 | −1.80 → −2.77 | +2.7 → +1.4 | — |
| forest ≥ 5 m at 0 m | 0 → 3.0 % | 0 → 8.0 % | 0 → 1.3 % | — |
| r² | 0.855 → 0.846 | 0.45 → 0.66 | 0.42 → 0.55 | 0.46 → 0.35 |
| RMSE (m) | 3.19 → 3.45 | 6.20 → 4.48 | 7.19 → 5.22 | 1.62 → 1.29 |

Night alone, CanElevation: forest ≥ 10 m −1.44 → −2.99 m, r² 0.81 → 0.77. Dropped heights were today's worse ones (mean
absolute error 2.9 vs 1.9 m CanElevation, 5.6 vs 3.1 m G-LiHT; 31–50 % over forest ≥ 5 m). Seward field: bias +0.5 → −1.0 m.
**Reading:** for the training pool v0.6 fails the tall-forest rule on both canopy-height-model references. A diagnostic
(keep today's height where v0.6 reports ≥ 2 m; not tuned, not adopted) recovers only part (CanElevation −2.1 m) because
v0.6's zeros over forest also lower the bias. Cause on record: night canopy photons labelled noise (v0.6 0.19 vs ATL08 0.11,
notebook 03) and the ground under dense canopy (entry below). Decision for training is Paul Montesano's.

## 2026-10-18 · Ground vs lidar DTM by canopy height (G-LiHT, CanElevation); v0.6 drops v0.5's 3-photon minimum

**Question (Paul Montesano):** is v0.5's tall-forest loss on CanElevation caused by the ground? Our ground surface (height −
relief at every photon, median per 30 m segment) minus the lidar DTM (11 m footprint mean), by lidar canopy height class.
CanElevation DTMs are orthometric: each box is shifted by the median v0.4 error over its bare segments (41 boxes with ≥ 5 bare
segments, 13,225 segments).

| CanElevation, lidar RH98 | v0.4 median / > 1 m too high | v0.5 median / > 1 m too high | v0.5 ground > 1 m above v0.4 |
|---|---|---|---|
| 0–1 m | 0.00 / 1 % | 0.00 / 1 % | 2 % |
| 5–10 m | +0.04 / 8 % | +0.06 / 10 % | 5 % |
| 10–15 m | +0.06 / 14 % | +0.10 / 17 % | 8 % |
| 15–20 m | +0.16 / 22 % | +0.17 / 23 % | 12 % |
| 20 m + | +0.23 / 30 % | +0.34 / 33 % | 15 % |

G-LiHT shows the same pattern, smaller (tall forest: median +0.08–0.10 → +0.11–0.13 m; > 0.5 m too high 19–26 → 21–27 %).
**Findings:** (1) in **every** version the ground sits too high under tall forest (a fifth to a third of 15 m+ segments by
> 1 m), part of the long-standing tall-forest underestimate; (2) v0.5 makes it worse in a tail: the v0.5 − v0.4 height
difference on CanElevation is < 0.1 m for 64 % of 15 m+ segments, but 8 % drop by > 2 m.

**Cause and fix.** Not the fraction: `dense_frac` 0.5, 0.25, 0.15 give the same CanElevation heights (20 m+ −3.34, −3.31,
−3.31 m). It is v0.5's extra minimum of 3 photons per layer: under dense canopy a 10 m bin often has only 1–2 ground photons,
so v0.5 started on a canopy layer. With no minimum (fraction test only), CanElevation, 6,809 common segments:

| | today | v0.4 | v0.5 | no minimum (v0.6) |
|---|---|---|---|---|
| bias 15–20 / 20 m+ (m) | −3.65 / −4.74 | −1.95 / −2.67 | −2.43 / −3.29 | −2.16 / −2.93 |
| r² / RMSE (m) | 0.728 / 3.87 | 0.775 / 3.61 | 0.760 / 3.72 | 0.770 / 3.65 |
| false vegetation | 14.4 % | 5.0 % | 4.3 % | 4.4 % |

G-LiHT harness: r² 0.553 (v0.4 0.514, v0.5 0.548), false vegetation 13.1 % (16.0, 13.0). **v0.6 = v0.5 with
`ground.dense_min_photons: 1`.** This setting was chosen with CanElevation in view (it is reported as such; methods §7). Known
limit (synthetic test): with ≤ ~2 ground photons per bin under very dense canopy every density-based first guess starts on a
canopy layer, where v0.4's envelope does better; that is the remaining ~0.25 m tall-forest gap to v0.4 on CanElevation.
Tests: `test_v06_sparse_ground_under_dense_canopy`, `test_v06_keeps_v05_afterpulse_fix`. Run `runs/v0.6/` started 22:08.

## 2026-10-17 · v0.5 results: mixed; better short vegetation everywhere, tall forest ~0.5 m shorter on CanElevation

Run `runs/v0.5/` (all rc = 0, 17:20–20:45). Common segments of today, v0.4 and v0.5 per reference (`summary_all_references.csv`):

| reference | r² v0.4 → v0.5 | RMSE (m) | false vegetation | bias < 2 m (m) | bias ≥ 10 m (m) |
|---|---|---|---|---|---|
| CanElevation | 0.772 → 0.758 | 3.63 → 3.75 | 5.0 → 4.3 % | +0.35 → +0.30 | −2.23 → −2.62 |
| G-LiHT (dev) | 0.544 → 0.587 | 5.20 → 4.89 | 12.8 → 10.4 % | +1.22 → +0.87 | −2.69 → −2.81 |
| LVIS (low weight) | 0.463 → 0.467 | 6.02 → 5.92 | 6.4 → 5.6 % | +0.86 → +0.73 | +2.22 → +2.04 |
| Seward UAV (dev) | 0.157 → 0.136 | 2.72 → 2.70 | 9.8 → 7.4 % | +0.25 → +0.04 | — |
| Seward field (dev) | 0.035 → 0.019 | 3.85 → 3.91 | 6.2 → 6.2 % | −0.03 → −0.11 | — |

**Reading:** v0.5 lowers heights everywhere by ~0.1–0.6 m. Short vegetation and false vegetation improve at every
reference. On CanElevation (discrete-return, independent, the reference that counts most) tall forest gets shorter:
15–20 m −1.95 → −2.44 m, 20+ m −2.76 → −3.34 m, so r² and RMSE are slightly worse than v0.4 (still better than today:
−3.67 / −4.76 m). Likely cause: under dense canopy the lowest dense layer can be understory or lower canopy, so the
ground sits too high. Not adopted yet; next check the v0.5 ground vs the ALS DTM by canopy height on G-LiHT and CanElevation.
Coverage 50–64 % (not a target).

## 2026-10-17 · v0.5: the planned height rule does not help; ground placement instead (Paul Montesano's choice)

**Planned idea tested first (development sites, G-LiHT, 869 segments where v0.4 reports > 0 m):** four rules for "height
from the photons that make the excess significant" (presence-test peak, background-corrected RH95 / RH98, plateau of the
cumulative excess with k = 1 or 2). None fixes the false heights: best (plateau, k = 2) moves the 0–1 m class median error
+5.2 → +4.2 m and makes 10 m+ forest 0.4–1.3 m more negative; cumulative-excess rules overshoot (background is
overestimated by day: observed / expected photons 25–45 m above ground = 0.65). Dropped.

**Diagnosis of the 113 segments with ALS RH98 < 1 m and v0.4 > 0 m** (photon-level reference labels and ALS DTM):
30 % our ground > 1 m off (mostly too low, slopes ~6–9°); 25 % ground right but ground / near-ground photons above the
canopy floor called canopy; 40 % reference canopy inside some photon footprints although the segment RH98 is < 1 m (a
reference-metric effect, not an ICESat-2 error); 5 % noise. Night strong beams show the same +5 m median error as day, so
solar noise is not the main cause. Profiles (16 segments) show the ground pulled below a bright flat surface by photons
~2 m under it, and ground lost and interpolated metres below the photons.

**v0.5 (one idea, config `atl03_reclass_v0.5.yaml`, lib `lowest_dense_layer`):** the first ground guess per 10 m bin is the
lowest layer 2 × halfwidth_m thick holding at least half the photons of the bin's densest layer, instead of the 5th
percentile of signal photons; iterations unchanged. `dense_frac` = 0.5 fixed a priori; 0.25 gives nearly the same result.
Harness (2.75 M photons around the 2,719 G-LiHT segments, reproduces v0.4: coverage 55.6 vs 55.7 %):

| G-LiHT development sites | v0.4 | v0.5 |
|---|---|---|
| r² / RMSE (m) | 0.514 / 5.47 | 0.548 / 5.18 |
| false vegetation (ALS < 1 m, est. > 2 m) | 16.0 % | 13.0 % |
| forest ≥ 5 m at 0 m | 8.1 % | 8.7 % |
| coverage | 55.6 % | 54.8 % |
| bias 10–15 / 20+ m (m) | −2.34 / −2.92 | −2.47 / −3.13 |

Not taken: less ground smoothing (3 bins instead of 5) scored better (r² 0.58, false vegetation 11 %) but is a setting tuned
on Alaska. Ground error vs the ALS DTM (> 1 m in 12–13 % of segments; 36–40 % on slopes > 10°) did not change with any
variant: on slopes most of it is co-registration between ALS and photons (in 114 of 353 such segments no signal photon lies
within 1 m of the DTM). Tests: `test_v05_ground_not_pulled_down_by_afterpulses`, `test_v05_forest_height_kept`.

**LVIS weight (Paul Montesano):** LVIS is a waveform lidar whose noise floor is probably 0.5–1.0 m (to verify); report it,
weigh it less than discrete-return lidar and the drone transects, and do not tune or reject versions mainly on it.

**Seward field (2 m) added as a fifth reference** (Paul Montesano): `field_max_200` from notebook 01 (tallest field
height within 2 m of each field point inside the segment, max over the points; 182 segments, median 1.24 m). Notebook 11
tables and figures and the validation map (1,140 field points) include it. On v0.4 (103 common segments): bias today
+1.01 → v0.4 −0.20 m, false vegetation 28 → 7 %, but RMSE 2.0 → 4.0 m and r² 0.27 → 0.03: a few segments with heights far
too tall (the v0.5 target), and a point survey samples a 30 m segment sparsely.

**Run:** `runs/v0.5/run_logs/` (01–05 first, then 09, 10 comparing v0.4 and v0.5, then 11). Notebook 11 now loads every
version through the run-folder chain and adds a map of all references and the development / production test tiles.

## 2026-10-17 · v0.4 development-site notebooks (01–05) and notebook 11: all validation results together

**Runs:** 01–05 at v0.4 (11:36–14:11, all rc = 0; 02 rerun at v0.4 so the run folder is self-contained). v0.3 was never run
on the development sites, so here v0.4 is compared with v0.2 and today. Notebook 11 (common segments of today, v0.2, v0.3,
v0.4 per reference; no control):

| | today | v0.2 | v0.4 |
|---|---|---|---|
| G-LiHT (1,423): false vegetation | 31 % | 27.5 % | **13.6 %** |
| G-LiHT: bias < 2 m / ≥ 10 m (m) | +2.37 / −3.97 | +2.37 / **−2.65** | **+1.24** / −2.79 |
| G-LiHT: r² / RMSE (m) | 0.40 / 5.85 | 0.44 / 5.88 | **0.54 / 5.21** |
| G-LiHT: forest at 0 m / coverage | **1.2 %** / **87 %** | 11.0 % / 65 % | 8.1 % / 56 % |
| Seward (225): false vegetation / bias < 2 m | 43 % / +1.87 | 26 % / +1.17 | **12.5 % / +0.36** |

G-LiHT 2–10 m vegetation is ~1 m lower than in v0.2 (5–10 m: −1.18 → −2.02 m), consistent with the wider ground window on
slopes taking in low canopy (17 Oct diagnosis); to watch in v0.5.

**Notebook 11** (`11_validation_summary_for_presentation.ipynb`, for readers outside ICESat-2): five figure sets, each
under a plain-language lede: bias by height class (4 references), false vegetation and forest called bare, scatter today vs
v0.4, r² by light × beam, coverage; a bottom-line table; appendices on binning (control) and slope. Figures in
`runs/v0.4/figures/11_*.png` and `docs/figures/`. Colours: today gray, versions one blue ramp (darkest = latest), checked
with the dataviz palette rules (ported validator: normal-vision ΔE ≥ 15.6, CVD ΔE ≥ 14.6).

## 2026-10-17 · v0.4 independent validation (LVIS 2019, CanElevation): mixed; fewer wrong zeros and false vegetation, less coverage

Notebooks 09 and 10 at v0.4 (v0.3 vs v0.4, run 17 Oct 10:57–11:36). Common segments = every compared version reports a
height. Notebook 09/10 tables include the control; notebook 11 does not (it keeps bare segments with no ATL08 canopy
photons, where the control has no height), so its n is larger (LVIS 17,218 vs 13,136) and some numbers differ.

**Both references pooled** (notebook 11 definition, 24,215 common segments, today / v0.3 / v0.4):

| | today | v0.3 | v0.4 |
|---|---|---|---|
| false vegetation (ref < 1 m, ICESat-2 > 2 m) | 16 % | 7.2 % | **6.3 %** |
| forest ≥ 5 m written as 0 m | **0.7 %** | 6.2 % | 2.8 % |
| bias, ref < 2 m / ref ≥ 10 m (m) | +1.20 / −1.42 | **+0.65** / **+0.24** | +0.72 / +0.44 |
| r² / RMSE (m) | 0.49 / **4.95** | **0.56** / 4.96 | 0.52 / 5.45 |
| coverage, LVIS / CanElevation | **88 / 95 %** | 62 / 64 % | 51 / 52 % |

- **CanElevation (CHM reference, like G-LiHT): v0.4 is the best version on every measure except coverage**: bias 0–1 m
  +0.40 → +0.37, 1–2 m +1.36 → +0.63 m; false vegetation 6.6 → 5.4 %; forest at 0 m 7.7 → 4.8 %; r² 0.75 → 0.76; RMSE
  3.83 → 3.73 m; 20+ m bias −2.9 m (today −4.9). Tall-forest criterion: 19 of 24 cells as written (v0.3 19), 20 of 24
  restated (v0.3 18). Night weak-beam r² 0.52 → 0.62 (today 0.73).
- **LVIS: v0.4 trades.** Better: false vegetation 7.6 → 6.8 %, forest at 0 m 5.5 → 2.0 %, 1–2 m bias +2.03 → +1.60, 2–5 m
  +2.21 → +2.06 m, weak-beam r² (day 0.26 → 0.34, night 0.60 → 0.64), and slopes (1–5 m vegetation on slopes > 20°:
  +6.8 → −0.2 m; forest > 20°: +3.5 → +1.4 m). Worse: r² 0.51 → 0.46, RMSE 5.36 → 6.01 m, 0–1 m bias +0.26 → +0.62 m, and
  tall forest more positive (+1.0 → +1.8 m at 20+ m), partly because removing wrong zeros raises the mean (non-zero
  heights alone improved slightly, 10–15 m +2.60 → +2.35 m).
- **Why LVIS RMSE rose:** 1,058 segments that v0.3 wrote as 0 m now get a height in v0.4; their squared error rises from
  29.7k to 178.8k m² (RMS ~13 m). Presence is usually right (median reference 2 m, median v0.4 2 m) but 28 % of those
  heights are > 5 m and 24 % sit over bare ground: **the height is taken as RH98 of all canopy photons, which daytime noise
  inflates over short, sparse vegetation.** Segments v0.3 had as a height and v0.4 sets to 0 m improve (18.8k → 4.5k).
- **Coverage, why it fell 11 points:** of the segments v0.3 reported and v0.4 does not (LVIS 4,203; CanElevation 1,694),
  82–88 % were v0.3 zeros; 58 % (LVIS) / 73 % (CanElevation) are bare ground (those zeros were right), the rest vegetated
  (wrong zeros); 54–64 % are daytime weak-beam segments whose few photons cannot show that no 25 %-cover canopy is present.
  Loss by class (LVIS): 0–1 m 70 → 50 %, 1–2 m 63 → 49 %, 10+ m 53 → 51 %.
- One CanElevation box (`NL-Churchill_2019-1m_0`, 82 photons) gives no segment in any version (as in the v0.3 run).
- **Bug found and fixed during the run:** the vectorised segment table (16 Oct) failed (`KeyError 'rh98'`) when a track
  has no canopy photon at all (control binning of bare tundra, LVIS `…R2003_066755`, 922 segments). Fixed in
  `_segments_table`; 09 restarted. The v0.3 run (per-segment loop) was not affected.

**Reading:** v0.4 does what it was built for, against data never used to design it: far fewer forest segments written as
bare (5–8 % → 2–5 %) and fewer false heights, especially on slopes. It does not improve agreement overall on LVIS, because
(a) the height of newly detected short vegetation is unreliable and (b) it gives up coverage on weak daytime beams. Not
adopted for training yet. **v0.5 (one idea): measure the height of detected vegetation from the photons that make the
excess significant** (`presence_top_m`, the height where the presence test peaks, already computed), instead of RH98 of
all canopy photons; to be designed and checked on the development sites first, then judged once on LVIS / CanElevation.

## 2026-10-17 · Names: what each 30 m version is, and why some tables have no v0.1 (Paul Montesano's question)

**Question:** what is the difference between "ATL08 classes → our 30 m (check)" and "current v7 30 m", and why is there no v0.1?

**Answer.** Every 30 m height is made in two steps: label the photons (ground / canopy / noise), then cut them into 30 m
segments and compute heights (binning). "Current v7 30 m" and "check" use the **same photon labels** (NASA's ATL08 v007
classes); they differ only in the binning: SlideRule PhoREAL (as in our training files) vs our own code. The check exists only to
show how much of any difference between today's heights and ours comes from binning rather than from our photon classes. "v7"
was confusing because it is the NASA data release (007), which **every** version uses, and sounds like one of our versions.
v0.1 is not missing by mistake: it appears in the 14–15 Oct G-LiHT and Seward results, and was replaced by v0.2 (it lost tall
forest, −14 m above 20 m) before the independent validations existed, so those compare v0.2/v0.3 (and from now on v0.3/v0.4).

**New names** (lib `validation_lib.LABEL_*`, notebooks 01–10, methods, plan): a name says whose photon classes, then who binned:

| | binned by SlideRule PhoREAL | binned by our code |
|---|---|---|
| ATL08 v007 photon classes | **ATL08 · PhoREAL (today)** | **ATL08 · our binning (control)** |
| our reclassified photon classes | (not made) | **reclassified v0.N** |

**Also changed (Paul Montesano, 17 Oct):** every validation table and scatter plot reports **r²** instead of r
(`validation_lib.r_squared`; notebooks 05, 06, 09, 10). Correlation values in entries before 17 Oct are r.

## 2026-10-17 · v0.4: tell bare ground from vegetation correctly (slope-aware ground + one presence test)

**Why a v0.4.** The 16 Oct review showed v0.3's short-vegetation gains came from writing 0 m, and 6–12 % of forest ≥ 5 m was
wrongly 0 m. Before changing the rule, its failure was diagnosed **on the development sites only** (G-LiHT tiles, Seward;
26,324 v0.3 segments, 3,153 with a reference height), so LVIS and CanElevation stay independent for judging the result.

**Diagnosis 1 · false zeros.** Forest segments set to 0 m have ~2 canopy photons and 21–24 ground photons; the rule
"< 3 canopy photons or < 5 after background correction → 0 m" treated weak evidence as absence. Interior: 21 % of forest
≥ 15 m and 28 % of 5–10 m at 0 m. Zeros by reference class (all regions): 45 % (0–1 m), 37 % (1–2), 24 % (2–5), 18 % (5–10),
8 % (10–15), 4 % (15+).

**Diagnosis 2 · false vegetation on slopes.** A prototype presence test (all photons above the ground vs the background,
Poisson) found a strong excess (median 11σ, by night as by day) on 42 % of bare G-LiHT segments (cover 0, RH98 0.2 m), peaking
3.5–7 m above our ground. By along-track slope, bare segments testing "vegetated": 27 % (0–5°), 77 % (5–10°), 96 % (10–20°),
91 % (> 20°). On sloped bare Kenai segments our ground surface sat a median **2.7 m below the G-LiHT ground**, and the
photons 1–8 m above it were mostly reference ground / buffer photons. Cause: with a fixed ±0.6 m ground window, the first
guess (5th percentile per 10 m bin) sits at the downhill end of each bin and the upslope ground returns of the 11 m footprint
never enter the window. ATL08 has the same known weakness on steep terrain.

**What v0.4 changes (one idea: is there vegetation above a correctly found ground?)**
- **(A) Slope-aware ground.** Ground window = ±(0.6 m + 11 m / 2 × along-track slope), the vertical spread an 11 m
  footprint has on that slope; the canopy floor rises by the same amount (unchanged on flat ground). Instrument geometry
  only; across-track slope is not known from one beam.
- **(B) One presence test.** For each segment, all photons (any class) between the canopy floor and 60 m are compared with
  the solar background expected at each height (Poisson); vegetation is present if the maximum excess is ≥ 3σ. A 0 m height
  is written only if, in addition, a canopy covering 25 % of the footprint with reflectance ratio 0.5 would have produced a
  ≥ 3σ excess in the lowest 5 m; otherwise NaN. Present but < 3 canopy photons → NaN (`veg_unmeasured`). The < 3 / < 5
  canopy-photon 0 m rule is removed. 25 %, 0.5 and 5 m were fixed beforehand (ρ = 0.5 at the dark-canopy end of published
  ratios), not tuned on any site.

**Synthetic tests** (`tests/`, 12 pass): bare 20° slope → < 10 % of segments > 2 m; open 18 m canopy at 25 % cover under
1 MHz background → < 5 % at 0 m (v0.3: 20 %); bare flat ground → > 80 % at 0 m. At 15 % cover (below the design cover)
zeros fall 75 → 21 % by day and 39 → 5 % at 0.2 MHz.

**Development sites, v0.3 → v0.4** (all reported segments, per reference RH98 class):

| | 0–1 m | 1–2 m | 2–5 m | 5–10 m | 10–15 m | 15+ m |
|---|---|---|---|---|---|---|
| share at 0 m, v0.3 | 45 % | 37 % | 24 % | 18 % | 8 % | 4 % |
| share at 0 m, v0.4 | 44 % | 33 % | 21 % | **9 %** | **2 %** | **1 %** |
| coverage, v0.3 → v0.4 | 71 → 56 % | 75 → 66 % | 71 → 63 % | 59 → 48 % | 63 → 58 % | 61 → 58 % |
| non-zero bias, v0.3 → v0.4 (m) | +6.4 → +6.5 | +4.0 → +3.6 | +1.6 → +0.7 | +0.3 → −1.0 | −1.6 → −2.1 | −2.6 → −2.7 |

- **Spurious vegetation** (reference < 1 m, ICESat-2 > 2 m): 28 % → **16 %**; slopes 5–10°: 45 → 23 %; > 10°: 71 → 12 %.
- **Per region:** forest ≥ 5 m at 0 m falls in every region (Interior 5–10 m 29 → 14 %, 15+ m 22 → 9 %; Kenai 7 → 4 %,
  3 → 1 %). Common-segment bias in tall forest: Kenai 15+ m −3.05 → −2.61 m, Interior 15+ m −7.59 → −7.27 m; 10–15 m slightly
  more negative (Kenai −2.12 → −2.33, Interior −2.61 → −2.81 m).
- **Coverage:** the lost coverage is mostly the former wrong zeros, now NaN ("vegetation not detectable", 6 % of 5–10 m;
  "vegetation seen, < 3 canopy photons", 1–3 %). The largest NaN reason is unchanged: "too little signal" (30–43 % of
  segments per class; 60–67 % of weak-beam segments).
- **Not fixed (v0.5):** where vegetation is reported over bare flat ground, heights are still +6.5 m (mean; +4.0 m median).
  27 % of flat bare segments show a significant excess above our ground, peaking 1.7–2.6 m above it.
- Interior 5–10 m non-zero heights moved from −0.6 to −2.7 m: the wider window on slopes raises the canopy floor and can
  pull low canopy into the ground; watch in the independent results.

**Runs:** `runs/v0.4/`; notebooks 09, 10 (v0.3 vs v0.4), then 01–05 (development sites) at v0.4, one runner with a lock file
(`runs/v0.4/run_logs/`). Diagnosis scripts and tables: session scratch (`v04diag/`), summarised here.

## 2026-10-16 · Correction: v0.3's short-vegetation "gains" are mostly zeros (Paul Montesano's review)

The improvements reported for short vegetation (spurious vegetation 47 → 12 %, LVIS 0–1 m bias +3.4 → +0.7 m) come largely
from **segments set to 0 m**, not from better heights. Common segments, share of h_canopy = 0 and bias of non-zero heights:

| LVIS RH98 class | 0–1 m | 1–2 m | 2–5 m | 5–10 m | 10–15 m | 15+ m |
|---|---|---|---|---|---|---|
| zero share, PhoREAL 30 m (training data today) | 44 % | 9 % | 5 % | 1 % | 0 % | 1 % |
| zero share, v0.3 | 87 % | 44 % | 27 % | 12 % | 7 % | 6 % |
| bias of non-zero heights, PhoREAL 30 m (m) | +2.8 | +3.0 | +2.7 | +1.8 | +0.4 | −1.7 |
| bias of non-zero heights, v0.3 (m) | +5.2 | +4.1 | +3.5 | +3.2 | +2.6 | +1.8 |

CanElevation shows the same (v0.3 zeros 56 % at 1–2 m, 41 % at 2–5 m vs 12 %, 9 %). Consequences: (1) where v0.3 reports
a short-vegetation height it is **more** overestimated than today; (2) 6–12 % of segments in forest ≥ 5 m are wrongly 0 m
(−7 to −18 m each); (3) mean bias and the spurious-vegetation rate reward zeroing and must not be used alone. Cause: the
v0.2/v0.3 0 m rule (enough total signal but weak canopy evidence: < 3 canopy photons, < 5 background-corrected canopy
photons, or RH98 < 0.6 m); background correction leaves few canopy photons over real shrubs and sparse canopy by day.
The "solved for this stage" reading in the CanElevation entry below is withdrawn.

**Reporting from now on:** zero rate by reference height class (correct below ~1 m, wrong above ~2 m) and accuracy of
non-zero heights, alongside bias / RMSE; **r² instead of r** (r was a default in the scatter helper; r² is the convention).
LVIS r² by stratum, PhoREAL 30 m → v0.3: day strong 0.32 → 0.44, day weak 0.08 → 0.25, night strong 0.14 → 0.41,
night weak 0.42 → 0.53.

**Proposed names (pending Paul's confirmation):** "current v7 30 m (ATL08 classes → PhoREAL)" → **ATL08 v7 30 m
(PhoREAL)**; "ATL08 classes → our 30 m (check)" → **ATL08 v7 30 m (our binning)**; v0.x → **reclassified v0.x 30 m**. The
PhoREAL segments are ATL03 photons with ATL08 v007 photon classes binned to 30 m by SlideRule, not the ATL08 100 m product;
the 100 m h_canopy could be added as a separate baseline.

**v0.4 priority:** the 0 m rule. Report 0 m only with strong ground signal and enough photons above ground to have detected
canopy; otherwise "not enough signal". Judge on zero rate by class and non-zero accuracy.

## 2026-10-16 · Independent validation 2: Canadian lidar, NRCan CanElevation 2019–2025 (notebook 10)

Up to 3 random projects per province / territory (2019–2025, boreal tiles, no cities), 2 random 4 km boxes each; 1 m CHM =
DSM − DTM read from the remote COGs; ICESat-2 June–September of the lidar year. 57 boxes: 48 with photons, 5 without
photons, 4 without lidar data. 13,807 segments in 13 provinces / territories / agencies; **6,615 common segments**;
38 % from leaf-on (June–September) projects. Reference = CHM RH98 in each footprint (as G-LiHT, notebook 05).

| Common segments, mean bias (m) | current v7 30 m | check | v0.2 | v0.3 |
|---|---|---|---|---|
| CHM 0–1 m (2,871) | +1.74 | +2.00 | +0.67 | **+0.58** |
| 1–2 m (241) | +2.25 | +2.32 | +1.74 | **+1.48** |
| 2–5 m (758) | +0.47 | +0.44 | −0.02 | −0.26 |
| 5–10 m (1,025) | −0.88 | −0.94 | −0.86 | −1.18 |
| 10–15 m (651) | −2.40 | −1.97 | −2.33 | −2.60 |
| 15–20 m (558) | −3.85 | −2.22 | −2.42 | **−2.69** |
| 20+ m (511) | −5.21 | −3.54 | −3.20 | **−3.35** |

- **Spurious vegetation** (CHM < 1 m, ICESat-2 > 2 m): current v7 30.2 % → v0.3 **9.3 %**; lower in every region except BC
  (20 segments, 100 % in every version, including v7: ICESat-2 6–9 m where CHM < 1 m; more likely a reference issue, e.g.
  steep terrain or harvest after the lidar, than the method; to check).
- **Tall forest:** v0.3 less underestimated than v7 at 15–20 m and 20+ m (all regions), slightly more at 10–15 m
  (−2.60 vs −2.40). Acceptance criterion as written: v0.3 passes 15 of 25 region × class cells; failures concentrate in
  NWT 10–20 m (−2.5 vs −1.6; −1.6 vs −1.4) and NRCAN (one night-time box, North_East_Timber 2023: median v0.3 2.9 m, v7 7.6 m,
  CHM 14.2 m). v0.2 is slightly better than v0.3 in tall classes here (the plateau top trims ~0.3 m).
- **By signal (r, v7 → v0.3):** day strong 0.82 → 0.86, day weak 0.53 → 0.47, night strong 0.89 → 0.84, **night weak
  0.80 → 0.63** (bias −0.91 → −2.56). Against CHM, v0.3 loses accuracy at night and on weak beams, unlike against LVIS.
- **Coverage:** v0.3 0.52–0.88 vs v7 0.82–1.00.

**Combined reading of the two independent validations (LVIS 2019 + CanElevation):**
1. **Solved for this stage:** spurious vegetation over short vegetation (47 → 12 % LVIS; 30 → 9 % CHM) and short-vegetation
   bias (0–1 m: +3.4 → +0.7 m LVIS; +1.7 → +0.6 m CHM), in every region.
2. **Tall forest:** better than v7 above 15 m against both references; at 10–15 m about equal (LVIS +1.6 vs +0.4; CHM
   −2.6 vs −2.4).
3. **New problem to fix next (v0.4): night-time and weak-beam sparse canopy.** Against CHM, v0.3 underestimates at night
   (strong −1.1, weak −2.6 m) and r drops; likely the column test's minimum of 5 photons and the box filter's minimum of 4
   neighbours with near-zero background, which reject sparse real canopy photons at night.
4. **Coverage** (52–88 % vs 82–100 %) is the main cost; segments flagged "not enough signal" need a closer look by region.

## 2026-10-16 · Independent validation 1: LVIS 2019 (notebook 09) · v0.3 holds outside Alaska development sites

40 random ABoVE 2019 LVIS flight segments (8 per region), ICESat-2 June–September 2019; 35,869 segments with LVIS RH98 on
≥ 6 of 11 centre-line points; **15,837 reported by all four versions** (common segments). None of these regions were used to
set any v0.1–v0.3 parameter. Reference = mean LVIS RH98 (waveform; bare ground reads ~0.5–1 m).

| Common segments, mean bias (m) | current v7 30 m | check | v0.2 | v0.3 |
|---|---|---|---|---|
| all regions · LVIS 0–1 m (3,635) | +3.40 | +5.46 | +0.82 | **+0.67** |
| all regions · 1–2 m (2,447) | +2.95 | +3.80 | +2.29 | **+1.87** |
| all regions · 2–5 m (3,639) | +2.59 | +2.86 | +2.24 | **+1.86** |
| all regions · 5–10 m (3,342) | +1.81 | +1.83 | +2.59 | +2.12 |
| all regions · 10–15 m (2,021) | +0.38 | +1.12 | +2.15 | +1.64 |
| all regions · 15–20 m (651) | −1.82 | +0.56 | +1.20 | **+0.72** |
| all regions · 20+ m (102) | −1.51 | +1.58 | +0.27 | **+0.13** |

- **Spurious vegetation** (LVIS < 1 m, ICESat-2 > 2 m): current v7 46.8 % → v0.3 **12.2 %** (v0.2 13.0 %); per region
  Alaska Arctic 50 → 9 %, NWT 40 → 7 %, Prairies / Shield 40 → 9 %, Yukon / N BC 23 → 7 %, Alaska boreal 57 → 29 %.
- **r vs LVIS RH98 (v7 → v0.3):** day strong 0.57 → 0.66, day weak 0.28 → 0.50, night strong 0.38 → 0.64, night weak
  0.65 → 0.73.
- **v0.3 vs v0.2:** v0.3 is closer to LVIS than v0.2 in nearly every region × class cell; the plateau top rule (`top_k = 1`,
  chosen on development data) is supported by independent data, so it stays.
- **Coverage (share of segments with a height):** v0.3 0.61–0.65 vs current v7 0.82–0.95. The largest remaining cost.
- **Remaining errors:** mid-height forest (5–15 m) +1.6 to +2.1 m; Alaska boreal (outside the development tiles) short
  vegetation +2.3 to +4.1 m and spurious 29 %.
- **Tall-forest acceptance criterion as written** ("no more negative than current v7", classes ≥ 10 m with ≥ 10 segments):
  v0.3 passes 9 of 13 cells. 3 of the 4 "failures" are cells where current v7 **over**estimates (Alaska boreal 10–15 m
  +6.3 vs v0.3 +2.6; 15–20 m +10.0 vs −3.5; Yukon 10–15 m +1.75 vs +1.69) and v0.3 is closer to LVIS; the fourth is Alaska
  boreal 20+ m (n = 14: v7 +4.0, v0.3 −6.4). **Question for Paul:** restate the criterion as "|bias| no larger than the
  current v7 30 m, and not more negative where v7 underestimates"? Not changed here.
- Note: against LVIS the current v7 30 m underestimates tall forest much less (−1.5 to −1.8 m) than against G-LiHT CHM RH98
  (−5 to −9 m); waveform RH98 and discrete-return CHM RH98 are different quantities. Both references are kept.

## 2026-10-15 · v0.3 started: noise-robust canopy top; independent validation (LVIS 2019, CanElevation, NEON)

**Diagnosis: impossible heights.** In the v0.2 production test (tile 3638, July 2024) 1,087 of 53,552 segments had
h_canopy > 20 m and 407 > 30 m over tundra: many "canopy" photons (median 44), few ground (5), RH50/RH98 ≈ 0.16, 78 %
daytime, 90 % strong beams, concentrated in a few tracks. Photon profile (track 221_24_10, solar elevation 47°, background
~2 MHz): the ground surface is right; clumps of "canopy top" photons sit 20–40 m above it where ATL08 has nothing. Two
causes, both from very high solar background:
1. **Canopy-top recovery** accepted a photon with ≥ 2 neighbours in a ±15 m × ~4 m window, where ~2.3 noise photons are
   expected by chance at this background.
2. **Column test (v0.2):** the canopy top was the height of maximum photon excess over background; above the real canopy
   the excess is a random walk, so its maximum drifts upward when the background is high (also inflating shrub tops).

**v0.3 changes (instrument-based, no site inputs):** `canopy.toc_k_sigma: 3` (canopy-top neighbours must exceed the expected
background by 3 σ, Poisson, as in the noise filter); `column.top_rule: plateau`, `top_k` (the top is the lowest height whose
excess is within top_k background σ of the maximum; the tolerance is 0 when there is no background, so night-time canopy is
untouched). First version had a +1-photon floor that trimmed real night-time canopy tops; removed.

Tests on development data (photon-level; segment heights vs a photon-based reference proxy; not the footprint validation):
suspect track > 20 m segments 30 → 13 (k = 1) / 10 (k = 2); Seward bias 1–2 m +0.78 → +0.46 / +0.31 m; Kenai 20+ m
+0.6 → −1.3 / −3.2 m; night-time retention unchanged; `toc_k_sigma` alone has no measurable effect. **`top_k = 1` set as
default; final value to be chosen on the independent validation, reported per region**, since choosing it here would tune
to the development sites.

**Independent validation data (accessible, checked 15 Oct):**
- **LVIS 2019 gridded 30 m** (ABoVE_LVIS_VegetationStructure_1923): local on ADAPT (`userfs02/data/LVIS/2019/output/
  metrics/30`, 116,271 files; index names `LVISF3_*`, files `LVISF2_*`); 1,740 ABoVE 2019 flight segments (July mostly),
  1,579 overlap boreal tiles, 66 touch the development tiles (excluded). RH10–RH100 means, ZG, CC, shots per cell (~7);
  waveform RH reads ~0.5–1 m over bare ground. **Notebook 09** (`09_validation_lvis_independent.ipynb`): 8 random segments
  in each of 5 regions (Alaska boreal, Alaska Arctic, Yukon / N BC, NWT, Prairies / Shield); ICESat-2 June–Sept 2019;
  reference = mean LVIS RH98 along each segment; versions current v7, check, v0.2, v0.3 on common segments.
- **NRCan CanElevation HRDEM lidar** (open STAC, 1 m DSM + DTM COGs, EPSG:3979): 321 projects 2019–2025 in 50–70° N across
  all provinces / territories (QC 57, SK 54, YT 39, NRCAN 36, BC 34, NWT 27, ON 25, AB 17, NU 15, MB 11, …). Remote
  windowed reads work (~5 s per 2 km box). **Notebook 10** (`10_validation_canelevation_independent.ipynb`): up to 3 projects
  per province / territory, 2 random 4 km boxes each; CHM = DSM − DTM; ICESat-2 June–Sept of the lidar year; reference
  = CHM RH98 in each footprint (as notebook 05); leaf-on subset reported. No public Canadian Forest Service ALS archive found;
  this is the public federal / provincial collection.
- **NEON AOP CHM** (DP3.30015.001): BONA, DEJU, HEAL, TOOL, BARR, UNDE, STEI, TREE with flights 2019–2025, but downloads now
  require a NEON account / API token (NEON policy from 30 June 2026); data API returns 403 without it. Pending a token.
- Not yet: Fennoscandian national lidar (Finland NLS needs an API key; Sweden Lantmäteriet an account; Norway order-based).

**Runner:** v0.3 runs use a lock file (`runs/v0.3/run_logs/run.lock`) and record the papermill exit code correctly (the
first 09 attempt was logged rc=0 although it failed: fixed).

## 2026-10-15 · Summary deck version 2 (v0.2 results); canopy cover on hold; v0.3 started

- Deck updated in place (same link): slides 7–10 rebuilt with v0.2 figures and numbers, next steps = v0.3, tracker row v0.2
  (`docs/slides/outline.md` lists the changes). The canopy-cover slide was replaced by agreement-by-signal and coverage.
- **Paul Montesano (15 Oct): canopy cover is on hold; v0.3 focuses on fixing and validating the ATL03 → ATL08-style heights,
  with validation against LVIS and other accessible airborne lidar (NEON, Canadian, other boreal lidar).**

## 2026-10-15 · v0.2 results (notebooks 00–08 complete) and the v0.3 list

**Run:** finished 15:14. From 14:08 two runners overlapped (the first was not killed when the Claude Code session ended,
contrary to what was logged), running 05–08 and 00 twice with the same code and config. All 32 v0.2 Parquet outputs read
cleanly; the validation CSVs are from the later runner. Next time: a lock file so a second runner refuses to start.

**Heights vs G-LiHT on common segments** (segments all three versions report; mean bias, m; n in brackets):

| Region · reference height | current v7 30 m | v0.1 | v0.2 |
|---|---|---|---|
| Interior · 10–15 m (55) | −5.10 | −6.55 | **−2.76** |
| Interior · 15–20 m (15) | −9.02 | −12.63 | **−7.93** |
| Interior · 20+ m (6) | −10.62 | −14.51 | **−8.06** |
| Kenai · 10–15 m (126) | −2.14 | −6.07 | −2.26 |
| Kenai · 15–20 m (173) | −3.87 | −6.81 | **−2.48** |
| Kenai · 20+ m (68) | −6.01 | −8.50 | **−3.72** |
| all · 0–1 m (679) | +2.98 | +2.11 | +3.00 |
| all · 1–2 m (173) | +1.62 | +0.89 | +1.53 |

- **Tall-forest acceptance criterion:** met in 5 of 6 cells; **fails Kenai 10–15 m by 0.12 m** (−2.26 vs −2.14). Interior
  15–20 and 20+ m have only 15 and 6 segments. v0.2 therefore is not adopted, but the column test reverses v0.1's tall-forest
  loss: v0.2 is closer to the reference than the current v7 30 m in the tall classes.
- **Short vegetation:** no better than the current v7 30 m on G-LiHT (0–1 m: +3.0 m both). Spurious vegetation (ref < 1 m,
  ICESat-2 > 2 m, all segments each version reports): current v7 38 %, v0.2 28 %; Seward 44 % → 15 % (v0.1: 12.5 %).
  Seward bias where reported: 0–1 m +1.0 m (v7 +2.8), 1–2 m +2.3 m (v7 +1.7), 2–5 m +1.0 m (v7 +1.1).
- **Coverage:** v0.2 reports a height for ~70 % of segments (rest "not enough signal"); losses concentrate in day · weak
  beams (339 reported vs 783 for v7). 94–99 % of the G-LiHT photons are daytime.
- **By signal (r vs G-LiHT RH98, v7 → v0.2):** night strong 0.48 → 0.70, night weak 0.25 → 0.53, day strong 0.63 → 0.57,
  day weak 0.24 → 0.29. RMSE drops in every stratum except day strong (5.2 → 6.6 m).
- **Canopy cover:** still not usable. Fitted ρv/ρg 0.13 (Interior), 0.40 (Kenai), 0.52 (Seward), cover bias +20 to +47
  points, r ≤ 0.40. **Fitting with reference photon labels gives the same implausible ratios (0.11, 0.32, 0.46)**, so the
  problem is in the rate / fit method, not in our photon classification. The shot-count fix did not resolve it.

**v0.3 list (why each):**
1. **Short-vegetation overestimate** is now the largest error and is not fixed by v0.1 or v0.2. Next: per-segment
   diagnosis of which photons set RH98 over short vegetation (daytime noise just above the canopy window, ground surface
   placed too low, or the 0.6 m resolvable height), by day / night.
2. **Coverage:** check the low-signal threshold (15 background-corrected photons per 30 m) against the ATL08 ATBD, and
   look at bias as a function of signal to set it from data in every region.
3. **Tall forest:** remaining −2.4 to −4.1 m in classes ≥ 10 m; check the Kenai 10–15 m cell, and which reference
   percentile (RH95 / RH98 / RH100) matches best per height class.
4. **Overfitting:** leave-one-region-out for the column-test settings; slope × forest strata and LVIS 2017/2019 (v0.2
   items 5–6, not done) to widen validation beyond the two G-LiHT regions.
5. **Canopy cover:** revisit the Purslow et al. (2023) rate formulation (background correction, segment length, per-track
   fit) since even reference labels fail.
6. **Runner:** a lock file per run directory.

## 2026-10-15 · v0.2 work: validation-matching diagnosis, shot count, low-signal flag, canopy column test, figure style

**1 · Why the current v7 30 m agrees so poorly with G-LiHT (r = 0.43): diagnosis.** If segment footprints are placed in the wrong
spot on the G-LiHT canopy height model, every segment is compared with the wrong trees and the correlation drops even if the
heights are fine. Checks on the v0.1 validation table (25,348 G-LiHT segments; only 1,788 have an ATL08-classes height in our
binning, 2,323 a PhoREAL height):
- **Footprints are the right size:** median 29 m long (first to last photon), median 321 CHM pixels each (1 m), as designed.
- **Track shifts look unreliable:** of 185 per-track horizontal shifts from notebook 02, **46 % sit at the edge of the ±6 m search
  window**, which suggests the true shift is larger or the alignment score (median absolute deviation of ground photons vs the
  DTM) does not find it. Vertical offsets `dz` range −3 to +22 m; a geoid offset should be nearly constant within a region.
- **Agreement depends strongly on signal**, for the check version (ATL08 classes → our 30 m) vs G-LiHT RH98: r = 0.60 at night vs
  0.36 by day; 0.52 strong vs 0.24 weak beams; 0.17 Interior vs 0.41 Kenai; r rises from 0.43 to 0.53 with ≥ 20 canopy photons.
  Part of the low r is therefore real (daytime and weak-beam noise, and the narrow height range in the interior), not matching.
- **Shift scan (result):** for 2,302 validation segments with an ATL08-classes height (54 tracks with ≥ 15 such segments), the
  footprint was moved over the 1 m CHM in 2 m steps up to ±20 m each way (441 positions) and RH98 recomputed at each.
  - Pooled r vs shift distance: 0.44 at 0 m, 0.43 at 4–8 m, 0.41 at 16 m, 0.39 at 28 m. Best single shift (−2, +2 m): r = 0.45.
  - Per-track best shifts are scattered (median 9 m, SD ~10 m, random directions); even with each track's own best shift
    (optimistic, overfits) pooled r is only 0.55.
  - **Conclusion: footprint placement is not the cause of the low r.** At 30 m scale a few metres of misplacement barely
    matters. The low pooled r comes from ICESat-2 signal: night r = 0.60 and strong-beam r = 0.52 are close to published
    ATL08 vs ALS agreement; daytime and weak-beam segments with few canopy photons pull the pooled value down. Segment-level
    v0.1 numbers stand, but must be reported by day/night × beam.
  - **Changes from this:** (a) notebook 02 keeps a track's horizontal shift only if it clearly improves the ground fit over no
    shift (`reference_labels.offset_min_gain`), since the ±6 m grid often picks noise (46 % at the edge); (b) notebook 05
    reports every result by day/night × beam strength as well as pooled. The ±6 m search is not widened (no evidence for
    larger shifts), so notebook 02 does not get slower.

**2 · Shot count (fixed).** v0.1 counted distinct shot ids among a segment's photons, missing shots with no return (median 34
counted vs 43 actual), which inflated per-shot rates (`Ev`, `Eg`), cover and the guard. v0.2: shots = segment length / 0.7 m;
partial first/last segments of a track from the photon time span at 10 kHz (`segments.shots_from_length`).

**3 · Low-signal flag (added).** v0.2 reports `h_canopy` = NaN with `low_signal` = True where background-corrected ground +
canopy photons < 15 per segment (scaled from ATL08's ~50 per 100 m; to verify against the ATBD); 0 m only where signal is
sufficient and canopy evidence is weak or RH98 < 0.6 m. On 6 sample tracks: 0 m share 91 % → 52 %, 41 % flagged low-signal.

**4 · Canopy column test (added).** Tall, open canopy spreads few photons over tens of metres, so the box noise filter dropped
real canopy photons. New step: per 20 m along-track column, photons above the ground are sorted by height; the canopy top is
where the photon excess over the background expected in that height range (from the ATL03 background rate, Poisson) is
largest and significant. Only instrument quantities and a significance level; no site inputs. Settings chosen from a grid on
50 sampled tracks (25 Interior, 25 Kenai; `runs/v0.2/col_grid.csv`): k_sigma 5, min 5 photons, max vertical gap 5 m.

| Reference canopy photons kept as canopy | v0.1 | v0.2 |
|---|---|---|
| canopy ≥ 10 m, day | 0.48 | 0.65 |
| canopy ≥ 10 m, night | 0.25 | 0.60 |
| ground labelled canopy, canopy ≥ 10 m, night | 0.13 | 0.18 |
| noise labelled canopy, canopy < 5 m, night | 0.010 | 0.029 |

Cost: more night-time ground and noise photons labelled canopy; the effect on spurious tundra heights must be checked at segment
level (Seward). **Overfitting check pending:** settings were picked on pooled Alaska tracks; per-region results and
leave-one-region-out are required before adopting.

**Seward after notebook 01 (v0.2) · read version comparisons on common segments.** Spurious tundra heights 12.5 % → 14.6 %
(current v7 30 m: 43 %); mean bias vs drone height rose (0–1 m: +0.4 → +1.0 m; 1–2 m: +0.4 → +1.5 to +2.3 m). Cause checked:
raw canopy RH98 per segment barely changed (mean |Δ| 0.15–0.5 m) and photon labels on Seward are almost identical to v0.1. The
change is which segments get a height: v0.1 set 67 % of drone < 1 m segments to 0 m, mostly for low signal, which pulled the
mean bias down; v0.2 reports half of those as NaN (low signal). The segments that do get a height were already ~+1.9 m too
high in v0.1. **So shrub heights are overestimated by ~2 m where reported, in v0.1 and v0.2 alike** (to address next). A
"minimum column top 3 m" rule was tested and dropped (no effect on Seward photons; −0.01 tall-forest retention at night).
**From now on every version comparison reports (a) metrics on the segments both versions report and (b) coverage (share
of segments with a height),** since a shrinking set of reported segments moves mean bias without any real change.

**Speed (notebook 02).** The track-offset search reopened every G-LiHT strip (up to 60) and sampled point by point for each of
49 shifts per track: ~65 min for the smallest tile, ~8 h projected for four tiles. `reference_lib.MosaicSampler` opens the
strips once per track, reprojects once, skips strips out of reach and reads one window per strip; `sample_raster` reads a
window instead of point-by-point sampling. Results verified identical to the old code (values and offsets); 32 s → < 1 s for
four tracks. Run restarted from 02 at 11:29 (00 and 01 kept; 00 re-executed at the end for the map fix). That restart was
still slow: a sparse track across a whole-flight G-LiHT **mosaic** DTM made the window span the mosaic (~10 GB, re-read per
shift). Fixed by reading 1024 × 1024 px cells around the points, cached across shifts; verified identical (tile 3457: 3
tracks 265 s → 22 s; full tile, 51 tracks, 92 s; 22 of 51 keep a horizontal shift). Restarted from 02 at 12:08.

**8 · Figures.** `lib/plot_style.py`: shared style for all notebooks; vegetation-height colormap from the VHR/ICESat-2 height
review map (https://pahbs.github.io/maap_tools/maps/Review_maps_v3.1_height_VHR.html; 0–10 m, gray → browns → yellows →
dark green, reproduced from its 500 colour samples) for any canopy-height display; ESRI World Light Gray Canvas basemap
(contextily, added to the `atl03reclass` env) on every map. Maps in notebooks 00 and 08 updated; scatter panels square with r.

**Outputs by version.** Notebooks now use config v0.2 and write config-dependent outputs to `runs/v<version>/` (reclass,
segments, validation, cover, production, figures, labelled photons, offsets); downloads, fetched photons, PhoREAL and
inventories stay shared in the work directory.

## 2026-10-15 · Tall forest is a hard requirement; validation widened (LVIS, slope × forest, public ALS)

**Why tall forest matters:** the reclassified 30 m heights will train the models that predict AGBD across the circumpolar domain.
A height bias that grows with height becomes a biomass bias that grows with biomass, concentrated where most carbon is.

**Acceptance criterion for every config version from v0.2 on (Paul Montesano):** in each reference-height class ≥ 10 m, and in
each region, the mean bias of **reclassified photons → our 30 m** must be no more negative than the **current v7 30 m**, and
should be closer to 0. A version that improves short vegetation but fails this is not adopted. Reported per region, height
class, and slope × forest stratum.

**LVIS (decided to add):** the gridded 30 m product we made and archived at ORNL (`ABoVE_LVIS_VegetationStructure_1923`; 3,579
flight segments: 1,051 from 2017, 2,528 from 2019) is the better first choice over the L2 footprints:
- same 30 m scale as our segments and the maps; one file per metric; already used for map validation, so results compare;
- layers: RH010–RH100 (means), ground elevation `ZG_mean/min/max`, canopy cover at 18 thresholds from 0.2 to 15 m
  (`CC_gte_*`, good for tundra cover), LVIS shots per cell `lvis_pt_cnt`;
- 2019 flights coincide with ICESat-2 (G-LiHT gap is 1–5 years); covers interior AK, North Slope, NWT, Yukon
  (`tiles/lvis_2017_2019_tiles_NA.csv`: 516 NA tiles; 148 with both years).
- Limits: a full-waveform RH98 is not the same quantity as a discrete-return CHM RH98 (compare by height class; check which
  LVIS RH matches best); 30 m cells do not give photon-level labels (only coarse ground/canopy windows from `ZG` and RH100).
- The L2 footprints (LVISF2, ~20 m) are kept as a check where gridded cells have few shots, and for exact geometry.

**Slope × forest strata (decided to add):** slope classes (0–5°, 5–10°, 10–20°, > 20°) × forest / non-forest, computed from
**circumpolar layers** (Copernicus GLO-30 slope, ESA WorldCover tree class) so the strata mean the same thing in production;
reference-based strata (DTM slope, CHM cover) reported alongside as a check. Slope matters because ground and canopy photons
overlap in height on slopes, and ATL08 v6→v7 did not fix sparse-short-steep segments.

**Public airborne lidar for wider validation (to verify access per site before use):**
- **NEON AOP** (US; annual discrete-return lidar, CHM product DP3.30015.001): boreal/Arctic BONA, DEJU, HEAL, TOOL, BARR; boreal–
  temperate transition UNDE, STEI, TREE (Wisconsin, near WLEF). Repeat years match ICESat-2.
- **Canada:** Québec MRNF lidar derivatives incl. CHM, CC-BY 4.0 (Données Québec, Forêt Ouverte; large boreal coverage);
  Ontario Forest Resources Inventory leaf-on single-photon lidar with CHM/DTM (Managed Zone; Open Government Licence – Ontario)
  and Ontario Classified Point Cloud; NRCan HRDEM (CanElevation) 1 m DTM + DSM where lidar exists (mainly south of the
  productive-forest line; north mostly satellite DSM only); BC LidarBC. No general public Canadian Forest Service ALS archive found.
- **Eurasia:** Finland NLS laser scanning (national, open); Sweden Lantmäteriet "Laser data Download, forest" (CC0, 2018–ongoing,
  1–2 pts/m²; older national "NH" 2009–2019); Norway Kartverket høydedata (national, open); Estonia Maa-amet lidar (open).
  No open airborne lidar found for Russian / Siberian boreal; there, rely on field plots and LVIS-like analogues.

## 2026-10-15 · Segment-level results, canopy cover, production test (notebooks 04–08, config v0.1)

**Height vs reference (G-LiHT + Seward, 3,072 segments; mean bias, m):**

| Reference height | 0–1 | 1–2 | 2–5 | 5–10 | 10–15 | 15–20 | 20+ | spurious veg |
|---|---|---|---|---|---|---|---|---|
| current v7 30 m | +3.2 | +1.7 | +1.0 | −1.3 | −3.7 | −5.3 | −8.9 | 37 % |
| new (v0.1) | +1.4 | +0.3 | −1.4 | −4.5 | −8.1 | −10.0 | −14.0 | 21 % |

- Short vegetation improves (as on Seward); **tall forest gets much worse**. Two causes: canopy photons lost by the noise filter
  (02–03) and the guard writing 0 m for low-signal segments: it flags 61–66 % of G-LiHT segments.
- **Validation sanity concern:** even the current v7 30 m correlates only r = 0.43 with G-LiHT RH98 (RMSE 7–8 m, RMSE 9 m in the
  0–1 m class). That is far worse than published ATL08 vs ALS agreement in boreal forest, so the footprint matching or alignment
  in notebook 05 may be wrong. **Segment-level numbers are provisional until this is checked.**
- **Canopy cover does not work yet:** fitted ρv/ρg = 0.07 (Interior), 0.50–0.54 (Kenai), 0.42–0.58 (Seward), against 0.7–1.2 in
  Purslow et al.; cover bias +18 to +50 points, r 0.06–0.39. Likely causes: inflated per-shot rates (shot-count bug) and
  reference "canopy" including background photons. Not usable until those are fixed.
- **Training pool (07):** with the guard writing 0 m, median new height is 0 in most land-cover classes; the `low_signal` / NaN
  change is required before any training use.
- **Production (08) works:** tile 3638, July 2024: 7 granules, 24 million photons → 53,134 segments in 18 min, with provenance.
  Rough scale: ~1–1.5 h per tile-year (June–September) → ~35,000 tile-years for all tiles 2019–2025 (DPS, parallel).

**v0.2 list (in order):**
1. Check and fix the notebook 05 footprint matching / alignment (r = 0.43 for current v7 30 m is not credible).
2. Shots per segment from segment length (fixes `Ev`, `Eg`, cover, guard).
3. `low_signal` flag with `h_canopy` = NaN; 0 m only with enough signal and canopy RH98 < 0.6 m.
4. Noise filter adapted to canopy and beam strength (vertical window / neighbour count above ground; weak-beam settings),
   chosen by the per-region grid (worst region).
5. Rerun 01–07, compare v0.1 vs v0.2 per region.

## 2026-10-15 · Photon-level results with the corrected confusion (notebooks 02–03, config v0.1)

G-LiHT tiles 3457, 3553 (Interior), 3836, 3928 (Kenai) + Seward; ~880,000 photons with a reference label (not buffer, not disturbed).

| Reference canopy height | 0–1 m | 2–5 m | 5–10 m | 10–15 m | 15–20 m | 20 m+ |
|---|---|---|---|---|---|---|
| ground → canopy, ATL08 v007 | 0.05 | 0.09 | 0.11 | 0.12 | 0.17 | 0.16 |
| ground → canopy, reclassified v0.1 | 0.06 | 0.06 | 0.06 | 0.05 | 0.07 | 0.09 |
| canopy recall, ATL08 v007 | 0.57 | 0.81 | 0.83 | 0.82 | 0.81 | 0.74 |
| canopy recall, reclassified v0.1 | 0.60 | 0.75 | 0.68 | 0.59 | 0.49 | 0.36 |

- **Ground:** reclassification reduces ground → canopy (the source of spurious heights) in every class; fitted ground has ~0
  median error and slightly lower 90th-percentile error than the ATL08 ground in tall forest (0.80 vs 1.12 m at 15–20 m).
- **Canopy:** v0.1 loses canopy photons in tall forest and on weak beams (weak-beam canopy recall 0.33 day / 0.23 night vs
  ATL08 0.68 / 0.60). At night background is low, so this is a real loss, not a reference-label artefact. Cause: sparse canopy
  photons spread over 20+ m rarely have ≥ 4 neighbours in the 10 m × 3 m box; canopy-top recovery is not enough. Left as is,
  this would worsen tall-tree underestimation.
- **Random-forest benchmark** (held out by region) keeps canopy recall 0.76–0.85 with ground as good or better, so the
  information is in the photons; the rules need changing, not abandoning.
- **Per-region sensitivity grid** (noise k, ground half-width, min canopy relief) barely moves results (worst-region score
  1.30–1.32); the parameters that matter (noise window, neighbour count, beam-specific settings) were not in the grid.
- **Added to v0.2:** a noise filter adapted to beam strength and canopy (taller vertical window or lower neighbour count above
  the ground surface; weak-beam settings), with those parameters in the per-region grid. Segment-level effect on tall-forest
  heights to be read from notebook 05 first.

## 2026-10-15 · Bug: photon confusion matrices were wrong (fixed)

- `validation_lib.confusion` paired reference labels (original row index) with classes (new 0…n index); pandas aligned them by
  index, so photons were mismatched. All photon confusion matrices and rates in notebooks 01–03 before this date were wrong
  (e.g. notebook 02 showed 60–100 % of reference-canopy photons as ATL08 noise; computed directly, ATL08 labels 72–84 % of them
  canopy in every class above 2 m). Segment-height results were not affected (they use arrays).
- Fixed (positional pairing) with a regression test; notebooks 01–03 rerun.
- Related caveat for interpreting photon rates: reference labels are height windows, so solar-background photons inside the
  canopy window are labelled "canopy" by the reference; in daylight and tall canopy this inflates "canopy → noise" for any
  classifier. Photon rates should be read by day vs night (notebook 03 reports both).

## 2026-10-14 · Known issues found while writing the methods (to fix in v0.2)

- **Shots per segment** are counted as distinct shots that returned a photon; this undercounts shots in photon-starved
  segments and inflates `Ev` / `Eg` (affects canopy cover and the 5-photon guard). Use segment length / 0.7 m.
- **Flag meaning:** `short_veg_flag` mixes "short vegetation" with "too little signal" and writes 0 m for both. v0.2: separate
  `low_signal` flag with `h_canopy` = NaN; 0 m only when there is enough signal and canopy RH98 < 0.6 m.
- **Overfitting guard for v0.2 tuning:** the guard threshold and any other change are chosen by leave-one-region-out over
  Interior, Kenai and Seward, and reported per region; notebook 03's sensitivity grid to be changed from pooled to per-region.

## 2026-10-14 · First real run: Seward Peninsula transects (notebook 01, config v0.1)

9 transects, 473 30 m segments with a UAV reference height (CHM RH98 in the footprint); 84 % daytime; median 41 shots and 5
canopy photons per segment.

| Reference height | Set to 0 by guard (new) | Median error where kept: new / current v7 30 m | Share > 2 m: current v7 30 m → new |
|---|---|---|---|
| 0–0.5 m | 76 % | 1.35 / 1.37 m | 38 % → 7 % |
| 0.5–1 m | 44 % | 1.23 / 1.60 m | 56 % → 27 % |
| 1–2 m | 41 % | 1.09 / 1.35 m | 65 % → 41 % |
| 2–5 m | 38 % | 0.54 / 0.98 m | 80 % → 52 % |

- Spurious vegetation (reference < 1 m, ICESat-2 > 2 m): **current v7 30 m 50 % → new 12 %**. Mean bias +2.1 m → +0.1 m (the
  latter helped by zeros cancelling overestimates).
- **The guard is too aggressive:** every zeroed segment failed the noise-corrected 5-photon rule. It sets ~40 % of real shrub
  segments to 0 m.
- **ATL08 classes → our 30 m (check)** is much worse than the current v7 30 m from the same classes (+4.8 vs +2.1 m bias):
  PhoREAL's top-of-canopy handling removes scattered high photons that our binning keeps. The relevant comparison is current v7 vs
  new; notebook 04 tests the binning directly.
- Reference caveat: under dense alder the SfM DTM can sit ~2 m above the ground that all classifications find (e.g. Council 01).
- Open: Kougarok 03–05 returned only ~3,000–4,000 photons (others 70,000–520,000).
- **Decision (Paul Montesano):** wait for the G-LiHT results before changing the guard, so one change (v0.2) is judged on both
  datasets and by leave-one-region-out.

## 2026-10-14 · Unit tests: stray daytime noise sets segment height

- Synthetic bare ground with daytime background (3×10⁶ photons s⁻¹): only 25 of 1,057 background photons survive the noise filter
  as canopy, but 3–4 strays per 30 m segment passed the 3-photon guard and RH98 took the highest one (up to 35 m); 15 % of bare
  segments reported > 1 m.
- **Change (in v0.1 before any real-data run):** guard also requires ≥ 5 canopy photons after subtracting the background expected
  in the canopy window. Bare-ground test then passes.
- Remaining synthetic behaviour: at night heights are right (20 m forest → 18.9 m; 2 m shrubs → 1.9 m); in daylight short
  vegetation is still overestimated (1 m shrubs → 2.0 m) and ~10 % of real canopy segments are flagged.

## 2026-10-14 · Set-up decisions

- **ATL03 v007 granules looked up in CMR by name** and passed to SlideRule as `resources`, so the release and inputs are explicit
  and recorded (SlideRule's default release is not visible in a request).
- **Reclassification runs client-side** (in the notebook or a DPS job) on photons from SlideRule; SlideRule's server-side PhoREAL
  only uses ATL08 classes.
- **Reference labels follow Purslow et al. (2023)**, with DTM + CHM rasters instead of a simulated ALS waveform.
- **Vertical alignment per track** to the reference DTM absorbs datum differences: UAV SfM models on the Seward Peninsula have
  per-site vertical references (offsets +26 to −87 m between transects).
- **Validation tiles** (notebook 00): first selection put the "interior" tiles south of the Alaska Range (62.5–63.4° N) because
  2018 G-LiHT is there; corrected to interior ≥ 63.5° N, 2018 strips if ≥ 200 km² per tile → tiles 3457, 3553 (interior),
  3836, 3928 (Kenai), all 2018 G-LiHT.
- **Environment:** a full conda solve hung for hours twice; bare Python 3.11 + pip wheels builds in minutes
  (`environment/atl03reclass.yml`). Run with `PYTHONNOUSERSITE=1`.

## 2026-10-14 · Why reclassify photons instead of filtering training segments

- Considered first: Cook's distance quality control of training segments (Zhang & Liu 2023). Rejected: it can only drop
  segments, not correct them, and a linear screen over a 3×3-tile area would preferentially drop real tall, dense forest where
  reflectance saturates, biasing heights and biomass low.
- Known ATL08 problems in our domain: short (tundra) vegetation overestimated, tall trees and canopy tops underestimated. Both
  arise in the photon classification, so the fix goes there.
- ATL08 v6 → v7 did not fix spurious short-vegetation heights in Alaska (May 2026 comparison: tie in 194 tiles, v6 better in
  102, v7 better in 50).
