# ATL03 v007 reclassification: decisions and results log

**Summary slides for collaborators:** _Google Slides deck pending (needs the Google Slides connector); outline and figures in `docs/slides/outline.md`, `docs/figures/`._

**Newest entries at the top.** Each entry: what was decided or found, why, and what it changes. Methods as implemented:
`atl03_reclassification_methods.md`; plan: `atl03_reclassification_plan.md`. Terms as defined in both.

**Standing rule (14 Oct 2026, Paul Montesano):** the goal is to run this approach on **all circumpolar tiles for every year**.
Development uses interior Alaska, the Kenai and the Seward Peninsula, so every decision must be checked against overfitting to
those areas (methods §7): physical or instrument-based thresholds only, no inputs that exist only in Alaska, settings chosen by
leave-one-region-out, out-of-region results reported, and wider validation (LVIS 2017/2019 in Canada and Alaska, Fennoscandian
ALS, Eurasian data) before scale-out.

## Current status and next steps

**Status (15 Oct 2026):** config v0.1 implemented; notebooks 00–08 run on ADAPT; committed and pushed (`52d07e9`).
v0.1 reduces spurious short-vegetation heights but **underestimates tall forest more than the current v7 30 m**; not usable yet.

**v0.2 (in order):**
1. Check and fix the notebook 05 footprint matching / alignment (r = 0.43 for current v7 30 m vs G-LiHT is not credible).
2. Shots per segment from segment length (fixes `Ev`, `Eg`, cover, guard).
3. `low_signal` flag with `h_canopy` = NaN; 0 m only with enough signal and canopy RH98 < 0.6 m.
4. **Tall-forest canopy retention** (acceptance criterion below): canopy- and beam-aware noise filter, stronger canopy-top recovery.
5. Validation strata: slope class × forest / non-forest (circumpolar layers), reported for every version.
6. Add gridded LVIS 2017/2019 (ABoVE_LVIS_VegetationStructure_1923) as a second airborne reference.
7. Rerun 01–07; compare v0.1 vs v0.2 per region, per height class, per slope × forest stratum.

**Then, before scale-out:** wider validation (NEON boreal/Arctic, Canadian provincial ALS, Fennoscandian national ALS).
---

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
