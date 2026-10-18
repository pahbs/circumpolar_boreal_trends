# Methods: ATL03 v007 photon reclassification and reprocessed ATL08-style 30 m segments

**Version described:** config `v0.6` (`config/atl03_reclass_v0.6.yaml`), code in `lib/` · **Status:** v0.6 is the final version of this series; for the night / low-sun training pool it is a trade-off (LOG)
(18 October 2026) · **Plan:** `atl03_reclassification_plan.md` · **Decisions and results:** `atl03_reclassification_LOG.md`

This document describes exactly what the code does, so that the 30 m segments can be reproduced and reviewed. Every number
below is a config value; the function that implements each step is given in brackets. When the method changes, a new config
version is created and the version history (section 8) is updated; this document always describes the latest version, and
marks which version introduced each step ("since v0.N").

**Scope.** The method is meant for **all circumpolar boreal and tundra tiles and every year** of ICESat-2, not for the
validation sites used to develop it. Section 7 sets out how that is protected against.

## Terms

### Photons and their classes

| Term | What it is |
|---|---|
| **ATL03 v007 photons** | Every photon ICESat-2 recorded (signal and solar background), unclassified. "v007" (also written "v7") is the NASA data release; every version below uses release 007. |
| **ATL08 v007 photon classes** | NASA's noise / ground / canopy / top-of-canopy labels on those photons |
| **Reclassified photon classes** | Our labels on the same photons (section 2), from one config version |
| **Reference photon labels** | Labels from G-LiHT or UAV DTM + CHM (the truth; section 5) |

### 30 m segment versions: what each name means

Every 30 m height is made in two steps: (1) **label the photons** (ground / canopy / noise) and (2) **cut the labelled
photons into 30 m segments and compute the heights** ("binning"). The versions differ in who does each step, so each name
says both:

| | binned by SlideRule **PhoREAL** | binned by **our code** (`segment_metrics`) |
|---|---|---|
| labelled with **ATL08 v007 photon classes** | **ATL08 · PhoREAL (today)** | **ATL08 · our binning (control)** |
| labelled with **our reclassified photon classes** | (not made) | **reclassified v0.1 … v0.6** |

- **ATL08 · PhoREAL (today)** is what our AGBD training files contain today: NASA's photon classes, binned by SlideRule's
  PhoREAL with the settings of `process_atl08_boreal.py`. It is the baseline every version must beat. (It is not the ATL08
  100 m product; it is ATL08's photon classes at 30 m.)
- **ATL08 · our binning (control)** uses the *same* NASA photon classes as "today" but our own binning. It exists only to
  answer: "how much of the difference between today and the reclassified heights is due to binning rather than to the photon
  classes?" It is not a candidate product. (PhoREAL's top-of-canopy handling removes scattered high photons that our binning
  keeps, so the control overestimates more than today in short vegetation.)
- **reclassified v0.N** uses our photon classes and our binning with config `v0.N`. Each v0.N is one step of development
  (section 8); the newest one is the candidate.

**Why not every table shows every version.** A version is dropped from new comparisons once its successor replaces it.
v0.1 appears only in the first G-LiHT and Seward results (14–15 Oct): it lost tall-forest heights (−14 m above 20 m) and was
replaced by v0.2 before the independent validations (LVIS, CanElevation) existed. Those started at v0.2/v0.3; each run
folder `runs/v0.N` compares v0.(N−1) and v0.N, and older versions are read from older run folders (notebook 11 joins them).

**Former names** (LOG entries before 17 Oct 2026): "current v7 30 m (ATL08 classes → PhoREAL)" = ATL08 · PhoREAL (today);
"ATL08 classes → our 30 m (check)" = ATL08 · our binning (control); "reclassified photons → our 30 m (new)" = reclassified v0.N.

### Other terms

| Term | What it is |
|---|---|
| **Reference height** | 98th percentile of the 1 m reference CHM inside a segment's 30 m × 11 m footprint (LVIS: mean RH98 along the segment) |
| **Common segments** | Segments for which every compared version reports a height; versions are compared on these so differences are not due to different segment sets |
| **Coverage** | Share of segments with a height (not NaN) |
| **Zero share** | Share of segments with a height of exactly 0 m (right over bare ground, wrong over vegetation) |
| **Spurious vegetation** | Reference < 1 m but ICESat-2 > 2 m, as a share of reference < 1 m segments |

---

## 1. Input photons

- **Product:** ATL03 release **007** with ATL08 release 007 photon classes.
- **Granules:** looked up by name in NASA CMR (`short_name=ATL03`, `version=007`, bounding box of the area, June–September of
  each year) and passed to SlideRule explicitly, so the exact inputs are recorded with every output (`granules_from_cmr`).
- **Photons:** SlideRule `atl03x`, surface type land, ATL03 signal confidence 0–4 (**background photons kept**: the
  reclassifier needs them), `quality_ph = 0` (nominal), all six beams (`fetch_photons`).
- **Per-photon fields used:** height (ellipsoidal, ITRF2014), along-track distance `x_atc`, position, `background_rate`
  (photons s⁻¹), `solar_elevation`, ATLAS spot (strong beams = spots 1, 3, 5), shot identifier, the ATL03 photon weight
  (YAPC score), and the ATL08 v007 class (0 noise, 1 ground, 2 canopy, 3 top of canopy, 4 unclassified). ATL08
  `segment_landcover`, `segment_snowcover` and `msw_flag` are carried along.
- **Processing unit:** one *track* = one granule × beam (`track_id = rgt_cycle_gt`); all steps in section 2 run per track.

## 2. Reclassified photon classes (`reclassify` → `classify_track`)

The ATL08 classes are **not** an input. Photons of a track are sorted by `x_atc`.

### 2.1 Signal vs noise (`noise_filter`, config `reclass.noise`) · since v0.1
For each photon, count the other photons in a box of ±*W*ₓ along track and ±*W*_z vertically (*W*ₓ = 10 m, *W*_z = 1.5 m).
The background count expected in that box is Poisson with mean

  λ = R_bg · (2 · 2*W*_z / c) · (2*W*ₓ / Δ)

where R_bg is the ATL03 background rate of the photon (s⁻¹), *c* the speed of light, and Δ = 0.7 m the along-track shot spacing.
A photon is **signal** if its neighbour count ≥ max(λ + *k*·√λ, *n*_min), with *k* = 3 and *n*_min = 4.

### 2.2 Ground surface (`ground_surface`, `ground_halfwidth`, `lowest_dense_layer`, config `reclass.ground`) · since v0.1, slope window since v0.4, first guess since v0.5
1. Bin signal photons along track in 10 m bins; first guess = the **lowest dense layer** of each bin (v0.5–v0.6, below;
   v0.1–v0.4: 5th percentile of heights per bin).
2. Fill empty bins by linear interpolation and smooth with a 5-bin rolling median.
3. Keep signal photons within the **ground window** of the smoothed surface; re-centre each bin on the median of their
   residuals; record the robust spread (1.4826 × MAD) per bin.
4. Repeat 2–3 three times. The final surface, spread and along-track slope are interpolated to every photon.

**Ground window (v0.4).** An 11 m footprint on terrain of slope θ returns ground photons over ±(*D*/2)·tan θ around its
centre. The window is therefore

  *w*_g = 0.6 m + (*D*/2) · |*s*|,  *D* = 11 m (`icesat2.footprint_diameter_m`), *s* = along-track slope of the current surface

(v0.1–v0.3: a fixed 0.6 m). *Why:* with a fixed ±0.6 m, the first guess on a slope sits at the downhill end of each bin and the
upslope ground returns fall outside the window, so the surface stayed metres too low (median 2.7 m below the G-LiHT ground on
sloped bare Kenai segments) and ground returns were labelled canopy: 71 % of bare segments on slopes > 10° got false vegetation
(LOG, 17 Oct). Only the along-track slope is known from one beam; across-track slope is not added (a known limit).

**First guess: lowest dense layer (v0.5, v0.6).** In each bin, slide a layer 2 × 0.6 m thick up through the sorted signal
photon heights; the first guess is the median height of the **lowest layer holding at least half the photons of the bin's
densest layer** (`ground.start: lowest_dense_layer`, `dense_frac` 0.5). *Why:* photons a few metres below the surface that pass
the noise filter (detector after-pulses under bright or specular surfaces such as water, daytime clusters) pulled the 5th
percentile down, the iterations kept the surface metres too low, and the true surface was labelled canopy; such photons are
sparse next to the surface return. v0.5 also required ≥ 3 photons in the layer; under dense canopy a bin often has only 1–2
ground photons, so v0.5 started on a canopy layer and tall forest came out ~0.5 m shorter (CanElevation). v0.6 drops that
minimum (`dense_min_photons: 1`). *Known limit:* with ≤ ~2 ground photons per bin under very dense canopy, any density-based
first guess can start on a canopy layer, where the old lower envelope did better (LOG, 17–18 Oct).

### 2.3 Classes (`classify_track`, config `reclass.canopy`)
- **relief** = photon height − ground surface.
- **ground (1):** signal and |relief| ≤ *w*_g.
- **canopy floor** = max(0.5 m, 2 × local ground spread) + (*w*_g − 0.6 m), i.e. the v0.1 floor raised by the slope part of
  the ground window (v0.4; 0 on flat ground).
- **canopy (2):** signal and canopy floor < relief ≤ 60 m.
- **Canopy column test (since v0.2, `canopy_column_top`, config `canopy.column`).** Per 20 m along-track column, photons above
  the floor (any class) are sorted by relief; for each candidate top *z* the excess is *N*(*z*) − μ(*z*), with
  μ(*z*) = R_bg · 2/*c* · shots · (*z* − floor) the background expected below *z*. Where the largest excess is significant
  ((*N* − μ)/√(μ + 1) ≥ 5, *N* ≥ 5, photons not counted across a vertical gap > 5 m), photons between the floor and the column
  top are canopy even if 2.1 rejected them. *Why:* tall open canopy spreads few photons over tens of metres, so the box filter
  dropped real canopy (v0.1 tall-forest recall 0.36–0.49).
  **Plateau top (since v0.3):** the top is the lowest *z* whose excess is within 1 background σ of the maximum (`top_rule:
  plateau`, `top_k: 1`). *Why:* above the real canopy the excess wanders with the background, so its maximum drifted upward
  in bright daylight (> 30 m heights over tundra).
- **canopy top recovered (3):** a photon rejected in 2.1 is relabelled canopy if relief is above the floor, within 3 m above and
  not more than 1 m below the local canopy envelope (rolling maximum of canopy relief over ≈ 15 m), and enough such candidates
  lie within ±15 m along track: at least 2 and, since v0.3, at least λ + 3√λ for the background λ expected in that window.
- **noise (0):** everything else.

Outputs per photon: `class_new`, `relief_new`, `signal_new`, `ground_sigma_new`, `canopy_floor_new`, `ground_slope_new`.
For comparison only, `relief_atl08` is computed for every photon as height above a ground surface drawn through the **ATL08**
ground photons (median per 10 m bin, interpolated) (`native_relief`).

## 3. 30 m segments (`segment_metrics`, config `segments`, `reclass.short_veg`)

### 3.1 Binning and heights · since v0.1
- **Binning:** per track, segment index = floor(`x_atc` / 30 m). (Segment boundaries do not coincide exactly with PhoREAL's;
  ATL08 · PhoREAL (today) segments are matched by nearest position on the same track, ≤ 20 m.)
- A segment is built if it has ≥ 5 ground + canopy photons.
- **Heights** (canopy = classes 2 and 3): `h_canopy_raw` = 98th percentile of canopy relief; `h_max_canopy`, `h_mean_canopy`;
  canopy-only RH `rh25 … rh100` (as ATL08); GEDI-style RH `rh25_gedi … rh100_gedi` over ground + canopy relief with ground
  clipped at 0 (Purslow et al. 2023, §2.3.3); `h_te_median` = median absolute height of ground photons.
- **Shots per segment** (since v0.2): segment length / 0.7 m; partial first and last segments of a track from the photon time
  span at 10 kHz. (v0.1 counted only shots that returned a photon, which inflated per-shot rates.)
- **Photon rates per shot:** `Evr` = canopy photons / shots, `Egr` = ground photons / shots. Background-corrected:
  `Ev` = max(0, `Evr` − R_bg·(2/c)·*H*_c), `Eg` = max(0, `Egr` − R_bg·(2/c)·1.2 m), *H*_c = highest canopy relief − 0.6 m.
  `canopy_signal_photons` = `Ev` × shots, `ground_signal_photons` = `Eg` × shots.

### 3.2 Is there vegetation, and what is reported (`vegetation_presence`, config `short_veg`) · v0.4
Each segment gets exactly one of three answers: **a height**, **0 m** (vegetation demonstrably absent), or **NaN** (cannot
tell). The decision comes from one statistical test plus one detectability check:

1. **Presence test** (config `short_veg.presence`). All photons of the segment (any class, so the test does not depend on how
   2.1–2.3 labelled them) with relief between the canopy floor and 60 m are sorted by relief. For each height *z*,
   excess(*z*) = *N*(*z*) − μ(*z*), μ(*z*) = R_bg · 2/*c* · shots · (*z* − floor). `presence_sigma` = max over *z* of
   excess / √(μ + 1). **Vegetation is present** if `presence_sigma` ≥ 3 (the Poisson 3σ used throughout).
2. **Detectability.** A canopy covering *c*_min = 25 % of the footprint with canopy/ground reflectance ratio ρ_min = 0.5 returns
   about *N*_g · ρ_min · *c*_min / (1 − *c*_min) photons for *N*_g background-corrected ground photons (Purslow et al. 2023,
   Eq. 1–2). It **would have been seen** if that is ≥ 3 · √(μ_layer + 1), μ_layer being the background expected in the lowest
   5 m above the floor (shrub layer). *c*_min, ρ_min and the 5 m layer were fixed a priori (ρ_min at the dark-canopy end), not
   tuned on any site.
3. **Answer:**

| Condition | `h_canopy` | flag |
|---|---|---|
| ground + canopy signal photons < 15 (since v0.2; ~50 per 100 m in ATL08) | NaN | `low_signal` |
| vegetation present, ≥ 3 canopy photons | canopy RH98 (0 m if < 0.6 m) | — |
| vegetation present, < 3 canopy photons | NaN | `veg_unmeasured` |
| not present, would have been seen | **0 m** | `short_veg_flag` |
| not present, would not have been seen | NaN | `low_signal` |

*Why (v0.4):* v0.2–v0.3 wrote 0 m wherever canopy evidence was weak (< 3 canopy photons, or < 5 after background
correction). Weak evidence is not absence: 6–12 % of forest ≥ 5 m against LVIS and CanElevation was set to 0 m (−7 to −18 m
each), and the improvement in short-vegetation bias came mostly from zeros (LOG, 16 Oct). The new rule writes 0 m only when a
canopy would have been detected and none was. Outputs: `presence_sigma`, `presence_top_m`, `veg_present`, `veg_detectable`,
`veg_unmeasured`, `ground_slope_deg` (median along-track slope, also used for slope strata).

*Earlier rules (for reading old results):* v0.1 set 0 m for < 3 canopy photons, RH98 < 0.6 m, or < 5 background-corrected canopy
photons, whatever the total signal. v0.2–v0.3 added `low_signal` (NaN) and kept the same 0 m rule for the rest.

- Carried per segment: position (mean, first and last photon), track, beam, strength, year, day of year, solar elevation,
  background rate, photon counts, ATL08 land cover / snow / water flags (mode).

## 4. Canopy cover (`fit_reflectance_ratio`, `canopy_cover`, config `cover`) · on hold since 15 Oct 2026

Following Purslow et al. (2023, *Sci. Remote Sens.* 7:100086, §2.2, §2.3.2), after Armston et al. (2013): background-corrected
rates lie on `Ev = Ev(100 %) − (ρv/ρg) · Eg`; one slope shared by all tracks of an area and one intercept per track (orthogonal
least squares, tracks weighted by r² of Ev vs Eg, ≥ 10 segments, negative correlation, `Ev(100 %)` and `Eg(0 %)` > 0.25 photons
per shot); `cv = 1 / (1 + (ρv/ρg) · Ng / Nv)`; fallback ρv/ρg = 1.0. Not usable yet: fitted ratios are implausible (0.1–0.5)
even with reference photon labels, so the problem is in the rate / fit formulation (LOG, 15 Oct). Paused while heights are fixed.

## 5. Reference data and labels (validation only; never used in production)

- **Development sites** (used to design the method): **G-LiHT** (LP DAAC `GLCHMT`, `GLDTMT` v001; tiles 3457, 3553 interior
  Alaska, 3836, 3928 Kenai; 2014/2018 flights; ICESat-2 2019–2020) and the **Seward Peninsula 2024 transects** (UAV SfM DSM and
  DTM at 1 m, field heights).
- **Independent sites** (never used to set a parameter, except that the v0.3 `top_k` was confirmed on LVIS): **LVIS 2019**
  gridded 30 m (`ABoVE_LVIS_VegetationStructure_1923`; 40 random flight segments in 5 regions of Alaska and western Canada;
  ICESat-2 June–September 2019; reference = mean LVIS RH98 along the segment, waveform; bare ground reads ~0.5–1 m) and
  **NRCan CanElevation** lidar 2019–2025 (up to 3 projects per province / territory, 2 random 4 km boxes each; CHM = DSM − DTM;
  ICESat-2 June–September of the lidar year).
- **Footprint surfaces** (`footprint_surfaces`): per 1 m cell, mean DTM within an 11 m circle (reference ground) and that ground
  + maximum CHM within the circle (reference canopy top).
- **Track alignment** (`track_offsets`, G-LiHT): per track, horizontal shift (±6 m, 2 m steps; kept only if it cuts the ground
  misfit by ≥ 20 %, since v0.2) and vertical offset minimising the median absolute deviation of ATL08 ground photons about the
  1 m DTM. CanElevation and LVIS: no shift (notebook 05's shift scan showed it does not change the result).
- **Reference photon labels** (`reference_label`, after Purslow et al. 2023, Fig. 1): with *z* = height − reference ground,
  ground if |*z*| ≤ 0.5 m; canopy if 0.5 m < *z* ≤ (reference canopy height + 1 m); noise if more than 5 m above the canopy
  window or more than 5 m below the ground window; otherwise buffer (excluded).
- **Disturbance screen:** photons where Hansen GFC v1.12 shows loss in or after the ALS year are excluded.
- **Caveats:** SfM DTMs can sit above the true ground under dense shrubs; 1–10 year gap between G-LiHT and ICESat-2; waveform
  RH98 (LVIS) and discrete-return CHM RH98 are different quantities; some CanElevation projects are leaf-off.

## 6. Evaluation

- **Photon level** (development sites): row-normalised confusion of reference labels vs each classification, by reference
  canopy height, day/night and beam strength.
- **Segment level**, for every version, on **common segments**, by reference height class (0, 1, 2, 5, 10, 15, 20, 60 m) and by
  region:
  - mean bias, RMSE; **r²** (not r) of ICESat-2 vs reference height, by day/night × beam strength (since 17 Oct 2026);
  - **zero share and accuracy of non-zero heights** per class (since 17 Oct 2026; mean bias alone rewards writing 0 m);
  - **coverage** per version (on all segments, not only common ones);
  - spurious-vegetation rate;
  - **slope class** (0–5°, 5–10°, 10–20°, > 20°, along-track ground slope) × reference < 1 m / 1–5 m / ≥ 5 m (since v0.4);
  - sensitivity to the reference percentile (RH95 / RH98 / RH100).
- **Tall-forest acceptance criterion** (since v0.2): in each reference class ≥ 10 m and each region, the mean bias of the
  candidate must be no more negative than ATL08 · PhoREAL (today). A restated form (|bias| no larger, and not more negative where
  today underestimates) is reported alongside, pending a decision.
- **Final summary for outside readers:** notebook 11 brings every validation (G-LiHT, Seward, LVIS, CanElevation) together.

## 7. Generality: this is for all circumpolar tiles and years, not for the validation sites

1. **Thresholds must be physical or instrument-based, not site-tuned.** Noise and presence thresholds scale with the measured
   background rate (Poisson 3σ); vertical windows relate to ICESat-2 range precision and footprint size (the v0.4 slope window
   uses only the 11 m footprint); nothing depends on latitude, region or a site-specific map.
2. **No inputs that exist only in the validation areas.** No Alaska IfSAR, G-LiHT or local land cover in the production path.
   Any optional prior (e.g. a ground DEM) must be circumpolar (FABDEM, Copernicus-based) and shown with and without it.
3. **Choose settings by held-out regions.** Parameter changes are judged per region (Interior, Kenai, Seward), and a change
   is adopted only if it does not degrade any region; any value chosen on independent data is reported region by region.
4. **Prefer simple rules to many parameters.** The random-forest benchmark (notebook 03) is a check, not the product.
5. **Widen validation before scaling out:** LVIS 2019 and CanElevation are done (notebooks 09, 10); still to add: NEON AOP
   (token needed), Fennoscandian national ALS (Finland, Sweden, Norway), Estonia; field plots for Siberia.
6. **Check across years and conditions:** stable-forest consistency between years, solar elevation, beam strength, season.
7. **The reflectance ratio needs a map, not a constant** before cover is used outside the validation sites.
8. **Report out-of-region performance** in every results summary, not only pooled numbers.
9. **Tall forest must not get worse** (section 6): these heights train the circumpolar AGBD models, so a height bias that grows
   with height becomes a biomass bias concentrated where most carbon is.
10. **Strata reported for every version:** reference class × region × slope class, plus day/night × beam.

## 8. Version history: the central idea of each version

Each version changes one idea, chosen from the previous version's largest error. Details and numbers: LOG.

| Version | Date | Central idea | What changed | Why (evidence) | Main result |
|---|---|---|---|---|---|
| **v0.6** | 18 Oct 2026 | **v0.5's ground, without losing sparse ground under dense canopy** | `ground.dense_min_photons` 3 → 1 | v0.5 raised the ground > 1 m in 8–15 % of CanElevation segments ≥ 10 m (ground vs CanElevation DTM): bins with 1–2 ground photons failed the 3-photon minimum | Independent CanElevation, same segments: r² 0.775 (v0.4) / 0.760 (v0.5) / 0.770; false vegetation 5.0 / 4.3 / 4.4 %; 20 m+ forest −2.67 / −3.29 / −2.93 m (today −4.74). G-LiHT r² 0.575 (v0.4 0.545). **Final of this series.** Training pool (strong beams, sun < 5°): false shrubs removed (CanElevation 6 → 2 %) but forest ≥ 10 m ~1 m shorter than today (−1.7 → −2.7 m), so not yet better than today for forest there. Remaining: tall forest 2–3 m short (ground too high under dense canopy in a fifth to a third of 15 m+ segments); one 38 m segment over Seward tundra (needs a plausibility cap) |
| v0.5 | 17 Oct 2026 | **Put the ground where the photons are** | first ground guess = lowest layer with ≥ half the densest layer's photons, not the 5th percentile | in v0.4's false heights over bare G-LiHT ground, the ground was > 1 m off in 30 % and ground photons were called canopy in 25 %; the planned height-from-excess rule was tested first and dropped (no gain) | Short vegetation and false vegetation better at every reference; tall forest ~0.5 m shorter than v0.4 on CanElevation (20 m+ −2.76 → −3.34 m). Replaced by v0.6 |
| v0.4 | 17 Oct 2026 | **Tell bare ground from vegetation correctly:** find the ground on slopes, and write 0 m only when vegetation would have been seen and was not | (A) ground window widens with along-track slope (± 0.6 m + 5.5 m × slope); canopy floor rises with it. (B) one presence test on all photons above the ground (Poisson 3σ) + a detectability check decide height / 0 m / NaN; the < 3 / < 5 canopy-photon 0 m rule is removed | v0.3's short-vegetation gains were mostly zeros, and 6–12 % of forest ≥ 5 m was set to 0 m; on development sites, 71 % of bare segments on slopes > 10° had false vegetation because the ground sat ~2.7 m too low | Development: forest set to 0 m 18 → 9 % (5–10 m), 4 → 1 % (15 m+); spurious vegetation 28 → 16 % (slopes > 10°: 71 → 12 %). Independent (LVIS + CanElevation): forest at 0 m 6.2 → 2.8 %, false vegetation 7.2 → 6.3 %; CanElevation best on all measures but coverage; LVIS r² 0.51 → 0.46 (heights of newly detected short vegetation unreliable); coverage 62–64 → 51–52 %. Not adopted for training |
| v0.3 | 15–16 Oct 2026 | **Stop solar noise from inventing tall canopy tops** | canopy-top recovery needs neighbours above the background by 3σ; column-test top = plateau (`top_k = 1`) instead of maximum | > 30 m "canopy" over tundra in bright daylight (tile 3638, 2024) | LVIS 2019: spurious vegetation 47 → 12 %, tall forest nearly unbiased; CanElevation: 30 → 9 %. Later found: short-vegetation gains mostly zeros |
| v0.2 | 15 Oct 2026 | **Keep sparse tall-canopy photons, and say "no data" instead of 0 m when signal is too weak** | canopy column test; `low_signal` NaN flag; shots from segment length; track shifts only when they help | v0.1 lost tall-forest canopy (−8 to −14 m at ≥ 10 m) and wrote 0 m for 61–66 % of G-LiHT segments | G-LiHT tall forest no more negative than today in 5 of 6 region × class cells (Kenai 10–15 m fails by 0.12 m); short vegetation no better; coverage ~70 % |
| v0.1 | 14 Oct 2026 | **Rebuild ground and canopy labels from all ATL03 photons** with instrument-based thresholds (no ATL08 classes) | noise filter, iterative ground, canopy classes, short-vegetation guard | ATL08 classes give spurious shrub heights (ground → canopy 9–17 %) and underestimate tall canopy | Seward spurious vegetation 50 → 12 %; tall forest much worse (canopy photons lost) |

## References
- Armston, J. et al. (2013). Direct retrieval of canopy gap probability using airborne waveform lidar. *Remote Sens. Environ.* 134:24–38.
- Hancock, S. et al. (2019). The GEDI simulator. *Earth Space Sci.* 6:294–310.
- Neuenschwander, A. et al. (2020). Validation of ICESat-2 terrain and canopy heights in boreal forests. *Remote Sens. Environ.* 251:112110.
- Purslow, M., Hancock, S., Neuenschwander, A., Armston, J. & Duncanson, L. (2023). Can ICESat-2 estimate stand-level plant structural traits? *Sci. Remote Sens.* 7:100086.
- Zhang, T. & Liu, D. (2023). Improving ICESat-2-based boreal forest height estimation by a multivariate sample quality control approach. *Methods Ecol. Evol.* 14:1623–1638.
