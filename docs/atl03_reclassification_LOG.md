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

**Status (15 Oct 2026, evening):** v0.2 run complete (notebooks 00–08, `runs/v0.2/`). Tall forest now **less**
underestimated than the current v7 30 m in 5 of 6 region × class cells ≥ 10 m (fails Kenai 10–15 m by 0.12 m); short
vegetation still overestimated where heights are reported; canopy cover still not usable. Not adopted yet. v0.3 list below.

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
