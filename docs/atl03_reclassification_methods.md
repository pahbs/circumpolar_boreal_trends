# Methods: ATL03 v007 photon reclassification and reprocessed ATL08-style 30 m segments

**Version described:** config `v0.1` (`config/atl03_reclass_v0.1.yaml`), code in `lib/` · **Status:** in development, first
validation runs (October 2026) · **Plan:** `atl03_reclassification_plan.md` · **Decisions and results:** `atl03_reclassification_LOG.md`

This document describes exactly what the code does, so that the 30 m segments can be reproduced and reviewed. Every number
below is a config value; the function that implements each step is given in brackets. When the method changes, a new config
version is created and the version table (section 8) is updated; this document always describes the latest version and
notes what changed.

**Scope.** The method is meant for **all circumpolar boreal and tundra tiles and every year** of ICESat-2, not for the
validation sites used to develop it. Section 7 sets out how that is protected against.

## Terms

| Term | What it is |
|---|---|
| **ATL03 v007 photons** | Every photon ICESat-2 recorded (signal and background), unclassified |
| **ATL08 v007 photon classes** | NASA's noise / ground / canopy / top-of-canopy labels on those photons |
| **Reclassified photon classes (v0.1)** | Our labels on the same photons (this document, section 2) |
| **Reference photon labels** | Labels from G-LiHT or UAV DTM + CHM (the truth; section 5) |
| **current v7 30 m (ATL08 classes → PhoREAL)** | 30 m segments from the ATL08 classes via SlideRule PhoREAL: our training files today |
| **ATL08 classes → our 30 m (check)** | Our binning (section 3) of the ATL08 classes: separates binning from classification |
| **reclassified photons → our 30 m (new)** | Our binning of the reclassified classes: the new product |
| **Reference height** | 98th percentile of the 1 m reference CHM inside a segment's 30 m × 11 m footprint |

---

## 1. Input photons

- **Product:** ATL03 release **007** with ATL08 release 007 photon classes.
- **Granules:** looked up by name in NASA CMR (`short_name=ATL03`, `version=007`, bounding box of the area, June–September of
  each year) and passed to SlideRule explicitly, so the exact inputs are recorded with every output (`granules_from_cmr`).
- **Photons:** SlideRule `atl03x` (client and server v5.6.3 at the time of writing), surface type land, ATL03 signal confidence
  0–4 (**background photons kept**: the reclassifier needs them), `quality_ph = 0` (nominal), all six beams (`fetch_photons`).
- **Per-photon fields used:** height (ellipsoidal, ITRF2014), along-track distance `x_atc`, position, `background_rate`
  (photons s⁻¹), `solar_elevation`, ATLAS spot (strong beams = spots 1, 3, 5), `pce_mframe_cnt` and `ph_id_pulse` (shot
  identifier), the ATL03 v007 photon weight (YAPC score), and the ATL08 v007 class (0 noise, 1 ground, 2 canopy, 3 top of
  canopy, 4 unclassified). ATL08 `segment_landcover`, `segment_snowcover` and `msw_flag` are carried along.
- **Processing unit:** one *track* = one granule × beam (`track_id = rgt_cycle_gt`); all steps in section 2 run per track.

## 2. Reclassified photon classes (v0.1) (`reclassify` → `classify_track`)

The ATL08 classes are **not** used. Photons of a track are sorted by `x_atc`.

### 2.1 Signal vs noise (`noise_filter`, config `reclass.noise`)
For each photon, count the other photons in a box of ±*W*ₓ along track and ±*W*_z vertically (*W*ₓ = 10 m, *W*_z = 1.5 m).
The background count expected in that box is Poisson with mean

  λ = R_bg · (2 · 2*W*_z / c) · (2*W*ₓ / Δ)

where R_bg is the ATL03 background rate of the photon (s⁻¹), *c* the speed of light, and Δ = 0.7 m the along-track shot spacing.
A photon is **signal** if its neighbour count ≥ max(λ + *k*·√λ, *n*_min), with *k* = 3 and *n*_min = 4.

### 2.2 Ground surface (`ground_surface`, config `reclass.ground`)
1. Bin signal photons along track in 10 m bins; first guess = 5th percentile of heights per bin.
2. Fill empty bins by linear interpolation and smooth with a 5-bin rolling median.
3. Keep signal photons within ±0.6 m of the smoothed surface; re-centre each bin on the median of their residuals; record the
   robust spread (1.4826 × MAD) per bin.
4. Repeat 2–3 three times. The final surface and spread are interpolated to every photon.

### 2.3 Classes (`classify_track`, config `reclass.canopy`)
- **relief** = photon height − ground surface.
- **ground (1):** signal and |relief| ≤ 0.6 m.
- **canopy (2):** signal and max(0.5 m, 2 × local ground spread) < relief ≤ 60 m.
- **canopy top recovered (3):** a photon rejected in 2.1 is relabelled canopy if relief is above the canopy threshold, within
  3 m above and not more than 1 m below the local canopy envelope (rolling maximum of canopy relief over ≈15 m), and at least 2
  such candidates lie within 15 m along track.
- **noise (0):** everything else.

Outputs per photon: `class_new`, `relief_new`, `signal_new`, `ground_sigma_new`.

For comparison only, `relief_atl08` is computed for every photon as height above a ground surface drawn through the
**ATL08** ground photons (median per 10 m bin, interpolated) (`native_relief`).

## 3. 30 m segments (`segment_metrics`, config `segments`, `reclass.short_veg`)

- **Binning:** per track, segment index = floor(`x_atc` / 30 m). (Segment boundaries therefore do not coincide exactly with
  the PhoREAL extents of the current v7 files; versions are matched by nearest position on the same track, ≤ 20 m.)
- A segment is reported if it has ≥ 5 ground + canopy photons.
- **Heights** (canopy = classes 2 and 3):
  - `h_canopy` = 98th percentile of canopy relief; `h_max_canopy`, `h_mean_canopy`.
  - **canopy-only RH** `rh25 … rh100` = percentiles of canopy relief (as in ATL08).
  - **GEDI-style RH** `rh25_gedi … rh100_gedi` = percentiles of ground + canopy relief, ground relief clipped at 0 (as in
    Purslow et al. 2023, §2.3.3; compatible with GEDI biomass models).
  - `h_te_median` = median absolute height of ground photons.
- **Photon rates per shot:** raw `Evr` = canopy photons / shots, `Egr` = ground photons / shots. Background-corrected:
  `Ev` = max(0, `Evr` − R_bg·(2/c)·*H*_c) and `Eg` = max(0, `Egr` − R_bg·(2/c)·1.2 m), where *H*_c = canopy window height
  (highest canopy relief − 0.6 m) and 1.2 m the ground window.
  *Known issue in v0.1:* "shots" = distinct shots that returned at least one photon; in photon-starved segments this undercounts
  the shots fired and inflates the rates. To be replaced by segment length / 0.7 m in v0.2.
- **Short-vegetation guard (new version only):** `short_veg_flag` = fewer than 3 canopy photons, **or** `h_canopy` < 0.6 m, **or**
  fewer than 5 canopy photons left after background correction (`Ev` × shots). Flagged segments get `h_canopy` = 0;
  `h_canopy_raw` keeps the unguarded value.
  *Known issue in v0.1:* the flag mixes "short vegetation" with "too little signal"; on the Seward transects it set ~40 % of
  segments with 0.5–5 m vegetation to 0 m (LOG, 14 Oct 2026). Planned for v0.2: separate `low_signal` flag with `h_canopy` = NaN.
- Carried per segment: position (mean, first and last photon), track, beam, strength, year, day of year, solar elevation,
  background rate, photon counts, ATL08 land cover / snow / water flags (mode).

## 4. Canopy cover (`fit_reflectance_ratio`, `canopy_cover`, config `cover`)

Following Purslow et al. (2023, *Sci. Remote Sens.* 7:100086, §2.2, §2.3.2), after Armston et al. (2013):

- In an area, background-corrected rates lie on `Ev = Ev(100 %) − (ρv/ρg) · Eg`.
- **Fit:** orthogonal least squares with one slope *m* = −ρv/ρg shared by all tracks and one intercept `Ev(100 %)` per track
  (absorbs differences in atmospheric transmission), Levenberg–Marquardt (`scipy.optimize.least_squares`). Each track is
  weighted by r² of Ev vs Eg; tracks need ≥ 10 segments and a negative correlation; tracks with `Ev(100 %)` or
  `Eg(0 %)` = −`Ev(100 %)`/*m* ≤ 0.25 photons per shot are dropped and the fit repeated.
- **Cover:** `cv = 1 / (1 + (ρv/ρg) · Ng / Nv)` per segment (0 if Nv = 0).
- **Fallback:** ρv/ρg = 1.0 where no fit is possible (to be replaced by a ratio map; section 7).
- Differences from Purslow et al., kept switchable: 30 m instead of 100 m segments; noise correction from the ATL03 background
  rate instead of a count of noise-window photons; photon classes from the reclassifier (production) or from DTM + CHM rasters
  (validation) instead of a simulated ALS waveform.

## 5. Reference data and labels (validation only; never used in production)

- **G-LiHT** (LP DAAC `GLCHMT`, `GLDTMT` v001; Alaska flights exist for 2014 and 2018 only). Validation tiles are chosen per
  region (interior Alaska ≥ 63.5° N; Kenai Peninsula) by largest 2018 strip area, if ≥ 200 km², otherwise 2014. ICESat-2
  growing seasons used: 2019–2020 for 2018 flights, 2019 for 2014.
- **Seward Peninsula 2024 transects:** UAV SfM DSM and DTM (resampled to 1 m: DSM maximum, DTM average; CHM = DSM − DTM) and
  field point heights.
- **Footprint surfaces** (`footprint_surfaces`): per 1 m cell, mean DTM within an 11 m circle (reference ground) and that ground +
  maximum CHM within the circle (reference canopy top).
- **Track alignment** (`track_offsets`): per track, horizontal shift (±6 m, 2 m steps) and vertical offset minimising the
  median absolute deviation of ATL08 ground photons about the 1 m DTM. The vertical offset absorbs datum differences
  (ellipsoidal ICESat-2 vs orthometric or arbitrary-datum references).
- **Reference photon labels** (`reference_label`, after Purslow et al. 2023, Fig. 1): with *z* = height − reference ground,
  ground if |*z*| ≤ 0.5 m; canopy if 0.5 m < *z* ≤ (reference canopy height + 1 m); noise if more than 5 m above the canopy
  window or more than 5 m below the ground window; otherwise buffer (excluded); none outside the reference.
- **Disturbance screen:** photons where Hansen GFC v1.12 shows loss in or after the ALS year are excluded (`hansen_lossyear`).
- **Reference height per segment** (`segment_footprints`, `als_segment_metrics`): rectangle from the first to the last photon,
  11 m wide, shifted by the track offset; CHM percentiles (50–100), mean, and cover fractions above 0.5, 1.37 and 2 m.
- **Caveats:** SfM DTMs can sit above the true ground under dense shrubs (reference heights too low); 1–10 year gap between
  G-LiHT and ICESat-2 (growth, undetected disturbance).

## 6. Evaluation

- **Photon level:** row-normalised confusion of reference labels vs each classification, by reference canopy height
  (0–2, 2–5, 5–10, 10–15, 15–20, ≥ 20 m), by day/night and beam strength. Key rates: ground → canopy, canopy → noise,
  noise → canopy.
- **Segment level:** bias, RMSE, MAE of `h_canopy` vs reference height by reference-height class (0, 1, 2, 5, 10, 15, 20, 60 m),
  for the three 30 m versions; spurious-vegetation rate (reference < 1 m, ICESat-2 > 2 m); share set to 0 by the guard;
  sensitivity to the ALS percentile used as reference (RH90–RH100).
- **Cover:** bias, RMSE, r vs lidar cover fraction (> 2 m for G-LiHT, > 0.5 m for Seward), with ρv/ρg = 1 and fitted.

## 7. Generality: this is for all circumpolar tiles and years, not for the validation sites

The validation data (interior Alaska, Kenai, Seward Peninsula) cover a small part of the domain, one continent, and mostly
2019–2020. Rules that keep the method from being fitted to them:

1. **Thresholds must be physical or instrument-based, not site-tuned.** Noise thresholds scale with the measured background
   rate; vertical windows relate to ICESat-2 range precision and footprint size; nothing depends on latitude, region or a
   site-specific map.
2. **No inputs that exist only in the validation areas.** No Alaska IfSAR, no G-LiHT, no local land cover in the production
   path. Any optional prior (e.g. a ground DEM) must be available circumpolar (FABDEM, Copernicus-based bare-earth) and its
   effect shown both with and without it.
3. **Choose settings by held-out regions.** Parameter changes are judged by leave-one-region-out performance (fit on two of
   Interior, Kenai, Seward, test on the third), and a change is adopted only if it does not degrade any held-out region.
   The sensitivity grid in notebook 03 reports per region, not pooled.
4. **Prefer simple rules to many parameters.** The random-forest benchmark (notebook 03) is a check, not the product; a learned
   classifier would only be adopted with region-held-out evidence and features that exist everywhere.
5. **Widen validation before scaling out:** Canadian and Alaskan LVIS 2017/2019 gridded heights (`tiles/lvis_2017_2019_tiles_NA.csv`),
   Fennoscandian national ALS (Finland, Sweden, Norway), and any Siberian ALS or field data, to cover Eurasian forest types,
   higher sun angles at lower latitudes, polar day, and snow conditions.
6. **Check across years and conditions:** the same tile in different years should give consistent heights where nothing
   changed (stable-forest test), across solar elevation, beam strength, and early vs late in the June–September season.
7. **The reflectance ratio needs a map, not a constant.** ρv/ρg varies with ground type; a circumpolar ratio (e.g. by land
   cover × region, fitted from ICESat-2 itself) replaces the fallback before cover is used outside the validation sites.
8. **Report out-of-region performance** in every results summary, not only the pooled numbers.

## 8. Version history

| Config | Date | Changes | Main results |
|---|---|---|---|
| v0.1 | 14 Oct 2026 | First implementation (sections 1–6). Short-vegetation guard extended with the noise-corrected 5-photon rule after a synthetic test showed stray daytime photons setting `h_canopy` to 35 m over bare ground. | Seward: spurious vegetation 50 % (current v7 30 m) → 12 % (new); guard sets ~40 % of 0.5–5 m segments to 0 (LOG) |
| v0.2 | planned | `low_signal` flag with `h_canopy` = NaN; shots from segment length; guard threshold set by leave-one-region-out over Seward + G-LiHT | |

## References
- Armston, J. et al. (2013). Direct retrieval of canopy gap probability using airborne waveform lidar. *Remote Sens. Environ.* 134:24–38.
- Hancock, S. et al. (2019). The GEDI simulator. *Earth Space Sci.* 6:294–310.
- Neuenschwander, A. et al. (2020). Validation of ICESat-2 terrain and canopy heights in boreal forests. *Remote Sens. Environ.* 251:112110.
- Purslow, M., Hancock, S., Neuenschwander, A., Armston, J. & Duncanson, L. (2023). Can ICESat-2 estimate stand-level plant structural traits? *Sci. Remote Sens.* 7:100086.
- Zhang, T. & Liu, D. (2023). Improving ICESat-2-based boreal forest height estimation by a multivariate sample quality control approach. *Methods Ecol. Evol.* 14:1623–1638.
