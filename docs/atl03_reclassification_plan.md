# Reclassifying ICESat-2 v7 ATL03 photons to build better 30 m vegetation heights and canopy cover

**Status:** v0.1 implemented, first runs on ADAPT (Oct 2026); see `atl03_reclassification_LOG.md` · **Drafted:** 14 Oct 2026 · **Owner:** Paul Montesano

## 1. Why

The 30 m ATL08 segments we train on come from ATL03 photons labelled by the ATL08 classifier (SlideRule `atl08p` with PhoREAL binning, files in `s3://maap-ops-workspace/montesano/data/process_atl08_boreal/030m/v007/{YEAR}/`). Their errors are not random:

- **Short vegetation is overestimated**, especially sparse tundra shrubs. Noise and ground photons just above the ground surface are labelled canopy, and `h_canopy` (the 98th percentile) picks them up.
- **Tall trees and the very top of the canopy are underestimated.** Canopy-top photons are sparse, the noise filter removes some of them (worse in daylight), and in dense canopy the ground is placed too high.

Moving from v6 to v7 did not fix the first problem. In `atl08_compare.ipynb` (May 2026, Alaska tiles), the false-vegetation rate in sparse, short strata was tied in 194 tiles, better in v6 in 102, and better in v7 in 50.

A filter on the training data, such as Cook's distance (Zhang & Liu 2023), can only drop bad segments. It can't correct the bias. Worse, it tends to drop real but nonlinear tall-forest cases. The fix has to happen where the error arises: in the photon labels.

**Goal:** a traceable, validated photon reclassification of ATL03 v7 that produces 30 m segments in the same schema as our current v7 files, plus a canopy cover estimate. It should have lower bias at both ends of the height range, be validated across height classes, and be ready to run on every boreal tile with SlideRule.

## Terms (used identically in the notebooks, tables and plots)

| Term | What it is |
|---|---|
| **ATL03 v007 photons** | Every photon ICESat-2 recorded (signal and background), unclassified |
| **ATL08 v007 photon classes** | NASA's noise / ground / canopy / top-of-canopy labels on those photons |
| **Reclassified photon classes (v0.1)** | Our labels on the same photons (`lib/icesat2_photon_lib.py: reclassify`, `config/atl03_reclass_v0.1.yaml`) |
| **Reference photon labels** | Labels from G-LiHT or UAV DTM + CHM (the truth) |
| **current v7 30 m (ATL08 classes → PhoREAL)** | 30 m segments from the ATL08 classes via SlideRule PhoREAL: our training files today |
| **ATL08 classes → our 30 m (check)** | Our binning of the ATL08 classes: separates binning from classification |
| **reclassified photons → our 30 m (new)** | Our binning of the reclassified classes: the new product |
| **Reference height** | 98th percentile of the 1 m reference CHM inside a segment's 30 m × 11 m footprint |

## Generality (standing rule)
The goal is to run this approach on **all circumpolar tiles for every year**, not just the Alaskan development sites. Every
change is checked against overfitting to them: physical or instrument-based thresholds only, no Alaska-only inputs, settings
chosen by leave-one-region-out with per-region results reported, and wider validation (LVIS 2017/2019 in Canada and Alaska,
Fennoscandian ALS, Eurasian data) before scale-out. Details: `atl03_reclassification_methods.md` §7.

## 2. Questions the work answers

1. How large are native ATL08 v7 errors, by height class, at the photon level and the 30 m segment level?
2. Does reclassification reduce them, and in which height classes, terrain and acquisition conditions (day/night, strong/weak beam, snow)?
3. What is the lower limit of height ICESat-2 can resolve in tundra? Below that limit we should report "short vegetation" rather than a number.
4. Can canopy cover be retrieved from classified photons once ground-reflectance variation is accounted for, and how well does it agree with airborne lidar?
5. How do the new 30 m segments change the training pool, and therefore the height and AGBD maps?

## 3. Data

| Role | Data | Notes |
|---|---|---|
| Photons | **ATL03 v007** (NSIDC, 2018-10 onward) via SlideRule | Confirm that SlideRule serves R007 and how to request it (step 0). |
| Baseline | **ATL08 v007** classes on those photons, and our existing v7 30 m files | The comparison target. |
| Field reference, tundra | **Seward Peninsula, Aug 2024**: 9 transects (Council 01–02, Kougarok 01–06, Teller 01) laid along ICESat-2 tracks | `/explore/nobackup/people/pmontesa/userfs02/projects/ilab/above_shrubs/data/field/sewardpen2024/`: point-intercept heights (`sew_pen_field_data_2024.gpkg`, 1,140 points), UAV SfM DSM/DTM, IfSAR, and earlier ATL03/ATL08 transect extracts (v6) |
| Airborne lidar reference | **G-LiHT** CHM, DTM and point cloud (LP DAAC: `GLCHMT`, `GLDTMT`, `GLLIDARPC` v001) | Alaska flights exist **only for 2014 and 2018**. Kenai: Aug 2014 and Jul 2018 (FIA and Kenai FHP lines). Interior: Jul–Aug 2014, Jul 2018. |
| Second airborne reference (optional) | LVIS (ABoVE 2017, 2019) | Closer in time to ICESat-2, but coarser footprint. |
| Disturbance screen | Alaska fire perimeters (AICC), Hansen GFC loss year | Needed because ICESat-2 is 1–10 years after G-LiHT. The **2019 Swan Lake fire** burned within the Kenai flight area. |
| Ground prior (optional) | Alaska IfSAR DTM (5 m) for development. For scale-out: FABDEM or a similar bare-earth DEM | Copernicus GLO-30 and ArcticDEM are surface models, biased by canopy. |

**Height range:** Seward tundra and shrub (0–3 m), interior Alaska spruce, birch and aspen (to about 25 m), Kenai spruce and birch (to 30 m or more).

## 4. Method

### 4.0 Inventory and setup
- Confirm the SlideRule client and server versions, how to request R007 ATL03, and which photon and ancillary fields are available (`atl03x`/`atl03sp`): ATL08 class, YAPC score, signal confidence, background rate, solar elevation, beam strength, transmit energy, segment id.
- Find the G-LiHT granules that intersect ICESat-2 tracks over our interior and Kenai tiles. Rank them by time gap, and screen out disturbed areas.
- Note the ATL03/ATL08 R007 changes that matter here, from the release notes and ATBD.

### 4.1 Reference photon labels (the "truth")
As in Purslow et al. (2023, §2.1.1, Fig. 1), photons are reclassified from the airborne lidar so that classification error can be measured. For every ATL03 photon within an airborne lidar or UAV footprint:
- height above the reference DTM: `dz = h_photon − DTM(x, y)`
- **ground** if `|dz| ≤ τ_g`, **canopy** if `τ_g < dz ≤ CHM_max + τ_c`, otherwise **noise**
- `τ_g` and `τ_c` set from ICESat-2 vertical precision and geolocation (about 3–5 m horizontal)
- sensitivity to a horizontal offset: test small shifts of the reference and keep the best one per granule-beam

These labels let us measure the native ATL08 confusion matrix by height class, and are the yardstick for the new classifier.

### 4.2 Photon reclassification (candidate algorithm, refined against 4.1)
Each step is a separate, testable function in `lib/`:
1. **Signal vs noise:** adaptive local density in along-track × height windows, scaled by the expected background count (background rate × window). YAPC score and ATL03 confidence are inputs, not the decision. Use different settings by day/night and beam strength.
2. **Ground surface:** robust iterative lower-envelope fit (for example, quantile spline or ground-percentile smoothing) with a slope-aware window. Optionally constrain it with a DEM prior (fixed tolerance, used only where ground photons are sparse). Report ground uncertainty per segment.
3. **Canopy and top of canopy:** photons above ground + `τ(ground uncertainty, beam, background)`. Keep sparse high photons when they are consistent across neighbouring shots, even where the noise filter alone would reject them.
4. **Short-vegetation guard:** when the canopy photons are not separable from the ground distribution (vertical spread within ground uncertainty, or few photons), label the segment **short vegetation / ground** and give its height as an upper bound, not a value. The Seward data sets this limit.

We'll also benchmark a second, data-driven option: a classifier trained on the 4.1 labels (features such as height above the fitted ground, local density, background rate, YAPC, beam, solar elevation), held out by site. It's only adopted if it clearly beats the rule-based version, and it ships with its own documented feature set.

### 4.3 30 m segments
- Identical along-track binning (30 m, same segment boundaries as our v7 files) applied to **both** the native ATL08 classes and the new classes. Any difference then comes from classification alone.
- Outputs: `h_canopy` (RH98), rh25…rh100, ground height and its uncertainty, canopy and ground photon counts and rates, `canopy_cover` (4.5), the short-vegetation flag, and the QA fields our filter uses today (`msw_flag`, `snowcover`, `sigma_topo`, `h_dif_ref`, etc.).
- Same parquet schema and naming as the current v7 files, plus new columns, so `extract_atl08_covars` and `mapBoreal` read them unchanged.

### 4.4 Validation of heights
- **Reference per segment:** airborne lidar metrics inside the actual segment footprint (30 m along track × ~11–13 m), not a pixel. Compare the ALS percentile that best matches RH98; Zhang & Liu found RH95.
- **Height classes:** 0–1, 1–2, 2–5, 5–10, 10–15, 15–20, 20+ m (reference height).
- **Metrics per class:** bias, RMSE, MAE, and the rate of spurious vegetation (segment height > 2 m where the reference is < 1 m). Each is shown for native v7 classes, reclassified photons, and our existing v7 files, and split by day/night, beam strength, slope and cover.
- **Seward:** compare transect profiles of photons, field point heights, UAV CHM and IfSAR. Report segment height against the transect mean and maximum, and against the UAV CHM.

### 4.5 Canopy cover from classified photons
Following Purslow et al. (2023, *Sci. Remote Sens.* 7:100086) from Hancock's group, which builds on the gap-probability approach used for GEDI (Armston et al. 2013; Hancock et al. 2019):

`cover = N_c / (N_c + N_g · ρ_c/ρ_g)`

where `N_c` and `N_g` are background-corrected canopy and ground photon counts (per shot, normalized for beam strength and transmit energy). The canopy:ground reflectance ratio `ρ_c/ρ_g` is the hard part. At 532 nm, ground reflectance ranges from dark (wet soil, burn scars, water) to bright (lichen, snow). That is the nonlinearity: a single ratio biases cover in opposite directions on different ground types.

- **Estimating the ratio (Purslow et al. 2023, §2.2):** background-corrected rates per shot, `Ev` (canopy) and `Eg` (ground), fall on a line `Ev = Ev(100%) − (ρv/ρg)·Eg`. Fit by orthogonal least squares with one slope shared by all tracks in an area and one intercept per track (absorbs atmospheric transmission), weighting each track by Pearson r² of Ev vs Eg; keep tracks with `Ev(100%)` and `Eg(0%)` > 0.25 photons per shot. They found ρv/ρg = 1.19 at Delta Junction, AK, and 0.69–0.93 at four temperate and Finnish sites; the fit fails where low-cover segments are missing (Wind River).
- **Implementation differences in v0.1** (switchable later): 30 m instead of 100 m segments; noise correction from the ATL03 background rate instead of the noise-window photon count; reference labels from 1 m DTM + CHM rasters instead of a simulated ALS waveform.
- **Fallback:** a ratio by land cover or ground type (ESA WorldCover, lichen/moss maps where available) when the local fit fails.
- **Snow:** exclude snow (ATL08 flag plus day of year), or handle it as its own ground class. It changes `ρ_g` by an order of magnitude.
- **Validation:** against airborne lidar cover computed the same way, as the first-return fraction above a height threshold (1.37 m and 2 m, plus 0.5 m for tundra). Use the Seward point intercepts for tundra. Report the error with and without the ratio correction.

### 4.6 Effect on the training pool and maps
On a few tiles (Seward, interior, Kenai): rebuild the 3×3-tile training pool from the new segments, and compare the height distributions by land cover and the AGB conversions. The new RH metrics must still match the definitions the GEDI-derived biomass models expect. Optionally, run `mapBoreal` and compare maps and boreal stock with the current v3.1 run.

## 5. Code layout (this repo)

```
lib/
  icesat2_photon_lib.py   # SlideRule requests, noise filter, ground fit, canopy labels, 30 m binning, cover, reflectance ratio
  reference_lib.py        # G-LiHT/LVIS search and download (earthaccess), footprint metrics, Seward loaders, disturbance screen
  validation_lib.py       # metrics by height class, confusion matrices, standard plots
config/
  atl03_reclass_v0.1.yaml # every threshold and window size, versioned
tests/
  test_icesat2_photon_lib.py  # synthetic-photon tests for each step
notebooks/atl03_reclass/
  00_inventory_and_setup.ipynb
  01_seward_transects_atl03_v7.ipynb
  02_reference_photon_labels.ipynb
  03_reclassifier_development.ipynb
  04_segments_30m_native_vs_new.ipynb
  05_height_validation_glihit.ipynb
  06_canopy_cover.ipynb
  07_effect_on_training_and_maps.ipynb
  08_sliderule_tile_production.ipynb   # scale-out: any tile list × years, same output schema, DPS-ready
docs/
  atl03_reclassification_plan.md       # this file
  atl03_reclassification_LOG.md        # decisions and results as they happen
```

**Traceability rules**
- Notebooks hold no algorithm code. They call `lib/`, show each step's effect, and record their inputs.
- Each output file records the git commit, config version and hash, SlideRule version, granule IDs and processing date in its parquet metadata.
- Every threshold lives in the config. Changing one means a new config version, never an edit to an existing one.
- Each notebook opens with its question and closes with a short results statement copied into the LOG.

**Key plots**
- Photon transect panels (native classes | reference labels | new classes) for one transect per site.
- Confusion matrices by height class.
- Segment height vs reference by height class for native and new, and bias per class as a single summary figure.
- Spurious-vegetation rate in tundra.
- Cover vs reference with and without the ratio correction.
- Ratio estimates by ground type.
- Training-pool height distributions, before and after.

## 6. Scale-out
`08_sliderule_tile_production.ipynb` and a DPS wrapper:
- SlideRule returns filtered photons for a tile and year.
- Reclassification and binning run client-side in the DPS job, because SlideRule's server-side PhoREAL only uses ATL08 classes.
- Output goes to `process_atl08_boreal/030m/reclass_v0.1/{YEAR}/` in the current schema.

The notebook reuses the patterns already in `icesat2_boreal/notebooks/tile_atl08_sliderule.ipynb`: the utexas organization, retries, the antimeridian truncation, and a missing-tile loop.

Run time per tile has to be measured first. Photon volumes are far larger than segment volumes, so the photon-level output is kept only for validation sites.

## 7. Other considerations

- **Physical limits:** pulse width and detector dead time put a floor on separating canopy from ground, on the order of 0.5–1 m and more on slopes. Below that, the honest answer is a flag, not a height. This matters most for tundra trends.
- **Time gap to G-LiHT** (2014/2018 vs 2018–2025): use the closest ICESat-2 years, remove burned or harvested areas, and expect some growth. LVIS 2019 is a cross-check.
- **Geolocation:** test offsets so horizontal error isn't counted as classification error.
- **Snow and season:** keep the growing-season, snow-free filter for heights. Snow is a separate problem for cover.
- **Day vs night:** solar background controls how many canopy-top photons survive. Report results separately, and check whether daytime segments should get a different flag or weight.
- **Consistency over time:** use the same algorithm and config for all years. Algorithm changes would otherwise show up as trends.
- **Downstream compatibility:** the biomass models and `mapBoreal` assume the current RH definitions and offsets. Any change in definitions needs a note and a check (4.6).
- **Platform:** git and notebooks in home on MAAP ADE (`/projects`), large outputs in buckets as `s3://` paths for DPS. Seward and G-LiHT preparation can run on ADAPT/Explore where those data already sit, and the results then move to S3.

## 8. Milestones

1. Inventory, reference labels, and native v7 error by height class (notebooks 00–02). The first decision point: how big is the problem, and where?
2. Reclassifier and segment comparison at Seward, interior and Kenai (03–05).
3. Canopy cover (06).
4. Effect on training and maps (07), then the decision to scale out.
5. Scale-out notebook and DPS run (08).

## References
- Zhang, T. & Liu, D. (2023). Improving ICESat-2-based boreal forest height estimation by a multivariate sample quality control approach. *Methods Ecol Evol* 14:1623–1638. doi:10.1111/2041-210X.14112
- Armston, J. et al. (2013). Direct retrieval of canopy gap probability using airborne waveform lidar. *Remote Sens Environ* 134:24–38.
- Hancock, S. et al. (2019). The GEDI simulator. *Earth Space Sci* 6:294–310.
- Purslow, M., Hancock, S., Neuenschwander, A., Armston, J. & Duncanson, L. (2023). Can ICESat-2 estimate stand-level plant structural traits? Validation of an ICESat-2 simulator. *Sci Remote Sens* 7:100086. doi:10.1016/j.srs.2023.100086
- Purslow, M. (2025). ICESat-2 measurements of forest structure & their utility for driving large-scale albedo simulation. PhD thesis, University of Edinburgh. hdl:1842/43155 (embargoed)
- Neuenschwander, A. et al. (2020). Validation of ICESat-2 terrain and canopy heights in boreal forests. *Remote Sens Environ* 251:112110.
- Cook, B. D. et al. (2013). NASA Goddard's LiDAR, Hyperspectral and Thermal (G-LiHT) airborne imager. *Remote Sens* 5:4045–4066.
