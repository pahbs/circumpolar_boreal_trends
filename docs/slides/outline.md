# Summary deck: ICESat-2 heights from reclassified photons (outline)

Source for the Google Slides deck linked at the top of `docs/atl03_reclassification_LOG.md`. Audience: collaborators who are not
following the details. Update this outline and the deck with every significant change to the methods or results.
Figures: `docs/figures/` (served from GitHub at `https://raw.githubusercontent.com/pahbs/circumpolar_boreal_trends/master/docs/figures/<file>`).

**Deck:** [Google Slides](https://docs.google.com/presentation/d/1L1QN_-S83ehHG6zJWZfWqqmeBviaDbzCudrvp0YADe0/edit)
**Deck version:** 2 · 15 Oct 2026 · describes config v0.2

**Version 2 changes (15 Oct 2026):** title → config v0.2; slide 6 canopy-top rule → column test; slides 7–10 rebuilt with
v0.2 results (7 Seward 44 % → 15 %, `01_segments_vs_uav.png`; 8 photon labels, `03_confusion_by_height.png`; 9 tall forest
on common segments, `05_version_comparison.png`; 10 agreement by signal and coverage, `05_by_signal.png`, replacing the
canopy-cover slide, now on hold); slide 11 image `08_production_test.png` (v0.2); slide 13 next = v0.3 list; slide 14
tracker with the v0.2 row. The slide texts below describe version 1; the LOG has the v0.2 numbers.

---

### 1 · Title
**Better ICESat-2 canopy heights by reclassifying photons**
Status update · config v0.1 · 15 October 2026 · Paul Montesano (NASA GSFC) · circumpolar boreal trends

### 2 · Why we are doing this
- Our biomass (AGBD) and height maps are trained on ICESat-2 **30 m heights built from NASA's ATL08 photon labels**.
- Those heights have two known problems in our domain:
  - **too tall over short vegetation** (tundra shrubs): ground and noise photons get labelled "canopy";
  - **too short over tall forest**: the few photons from the top of the canopy get thrown away as noise.
- Both errors start in how individual photons are labelled, so we relabel the photons ourselves.
- **Goal:** one method, run on **every circumpolar tile, every year**.
- Visual: `01_profile_council_01.png` (top row: ATL08 labels; scattered "canopy" photons above real shrubs).

### 3 · Words we use (keep this slide in every version)
- Visual: `terms_diagram.png`.
- One sentence: everything starts from the same photons; we compare three ways of labelling them, and three versions of the
  30 m heights built from them, against airborne-lidar truth.

### 4 · The approach in four steps
1. Download every ICESat-2 photon (release 007) for a place and year.
2. Relabel each photon as ground, canopy or noise with our own rules (no ATL08 labels used).
3. Bin the labelled photons into 30 m segments and compute canopy height (98th percentile of canopy photons above the ground).
4. Check against airborne lidar (G-LiHT) and drone models with field plots, by height class, region, slope and forest type.

### 5 · Where we test
- Visual: `00_inventory_map.png`.
- **Interior Alaska** (tiles 3457, 3553) and **Kenai Peninsula** (3836, 3928): 2018 G-LiHT airborne lidar, ~19 million photons.
- **Seward Peninsula**: 9 transects walked in Aug 2024 with drone surface models and field heights (tundra and shrubs).
- These are development sites only; wider validation comes before any large run (slide 12).

### 6 · How the relabelling works
- Visual: `03_steps_example.png` (one track, step by step).
- Step 1 **signal vs noise**: keep photons with clearly more neighbours than sunlight noise alone would give.
- Step 2 **ground**: trace the lowest dense layer of photons along the track.
- Step 3 **canopy**: signal photons clearly above the ground.
- Step 4 **canopy top**: rescue sparse photons just above the canopy that step 1 dropped.

### 7 · Result 1 · Tundra and shrubs (Seward): far fewer false heights
- Visual: `01_segments_vs_uav.png`.
- Segments where the drone says < 1 m but ICESat-2 says > 2 m: **50 % today → 12 % with relabelled photons**.
- Where a height is reported it is closer to the drone height in every class.
- **But** a safety rule sets ~40 % of real shrub segments to 0 m (too few photons in daylight). Fix planned (v0.2).

### 8 · Result 2 · Photon labels: better ground, but tall-canopy photons lost
- Visual: `03_confusion_by_height.png`.
- Ground photons mislabelled as canopy: lower than ATL08 in every height class (e.g. 0.07 vs 0.17 at 15–20 m).
- Canopy photons kept: **0.36 vs 0.74 (ATL08) in forest > 20 m**; worst on weak beams. The noise rule is too strict for sparse
  canopy photons.

### 9 · Result 3 · Heights vs airborne lidar: short better, tall worse (provisional)
- Visual: `05_height_validation.png`.
- Mean bias by lidar height: today +3.2 m (< 1 m) … −8.9 m (> 20 m); relabelled +1.4 m … −14.0 m.
- **Caveat:** even today's heights agree poorly with G-LiHT (r = 0.43), which suggests a problem in how we match segments to
  lidar. These numbers are provisional until that is checked (first item for v0.2).

### 10 · Canopy cover: not working yet
- Visual: `06_rates_and_ratio.png`.
- Method from Purslow et al. (2023): cover from canopy vs ground photon counts, corrected for how much brighter ground is than
  canopy at the laser's green wavelength.
- Fitted brightness ratios are implausible and cover is 18–50 points too high: a known counting issue to fix in v0.2.

### 11 · Running at scale works
- Visual: `08_production_test.png`.
- One tile, one month: 7 orbits, 24 million photons → 53,000 30 m segments in 18 minutes, with full provenance.
- All tiles 2019–2025 ≈ 35,000 tile-years: feasible on NASA MAAP, in parallel.

### 12 · Rules we hold ourselves to
- **Must work everywhere:** thresholds based on physics and the instrument, never tuned to a site; no Alaska-only inputs;
  settings chosen by testing on one region after tuning on the others; results reported per region.
- **Tall forest must not get worse** than today's heights (in every height class ≥ 10 m, every region): these heights drive
  biomass, and tall forest holds most of the carbon.
- **Wider validation before scale-out:** LVIS 2017/2019 (Alaska, Canada), NEON sites, Québec / Ontario / BC lidar, Finland /
  Sweden / Norway / Estonia national lidar.

### 13 · Next (config v0.2)
1. Check the matching of segments to lidar (slide 9 caveat).
2. Fix photon counting per segment (affects cover and the safety rule).
3. Report "not enough signal" as missing, not as 0 m.
4. Keep tall-canopy photons: noise rule that adapts to canopy and beam strength.
5. Add slope × forest/non-forest results and LVIS as a second lidar reference.

### 14 · Progress tracker
| Date | Version | What changed | Headline |
|---|---|---|---|
| 14–15 Oct 2026 | v0.1 | First implementation; 9 notebooks run end to end | Fewer false tundra heights; tall forest underestimated more; cover not working |
| next | v0.2 | Items on slide 13 | |

Links: plan, methods, LOG in `docs/`; notebooks in `notebooks/atl03_reclass/`.
