# Single-year vs multi-year ICESat-2 AGBD models: design log

Log for `model_strategy_single_vs_multi_yr.ipynb`.

---

## 2026-10-12: Shortcomings of the first version

### Prompt (Paul Montesano)

> there are a couple shortcomings in this notebook. first, we only can test year 2020 because the single-year model was only run for that year. One advantage of the multi-year model is that it produces many years' worth of correspondances between ICESat-2 and HLS. Second, this notebook doesnt address the extent to which one model vs the other improves estimates (whether by correctly increasing or decreasing them, and over which AGBD intervals) in a clear enough way. So, while it is clear that overall the difference in small between the 2 models, what is the affect on total AGB stock? Discuss this before doing anything

### Response (Claude)

Agreed on both points. Here's how I'd address them, plus what I'd need from you before changing anything.

#### 1. Only 2020 can be tested

This is a real limit, and 2020 is probably a favourable year for the single-year model. In your old notebook's output for one Siberian tile, the candidate ICESat-2 counts per year were:

| Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|
| Candidate obs | 21,900 | 88,223 | 16,365 | 108,653 | 11,824 | 116,331 |

In that tile, 2020 had about 5–7× as many observations as 2021 or 2023. A single-year model's weakness should show most in the poor years, which this notebook can't test. So the 2020 result likely understates the multi-year advantage.

There's also a second advantage the 2020 test can't capture. Each multi-year training obs is paired with HLS from its own year. The model therefore sees how the same structure looks under different years' reflectance, which should make its year-to-year predictions more consistent. That's partly what §5 (stability) gets at, but only indirectly.

**Options:**
- **A. Run the single-year model for one or two poor years on a subset of tiles** (e.g. 2021 and 2023, ~100 stratified tiles). This is the only direct test. The notebook already handles any year once it has a tile index; `TARGET_YEAR` and `RUNS` become lists. It costs a modest DPS run.
- **B. Without new runs, show what a single-year model would have had each year.** The multi-year training pool records each obs's year, so I can count, per tile and year, the obs a single-year model would have trained on. A map like that shows where and when single-year training would be thin, but not what the map error would be.
- **C. The v3.0 single-year height series (2019–2024)** already exists, but it's a different model version and height, not AGBD. It's only useful as supporting evidence, as now.

I'd do B now, since it's cheap and frames the problem, and A if you can afford the DPS run.

#### 2. How the estimates change, and what that does to total stock

You're right that "RMSD differs a little" isn't the useful answer. The questions are: where does the switch raise or lower estimates, is each change toward the truth, and what does it add up to over the domain? The answers to these can differ.

**Small mean differences can be large stocks.** A mean difference of 1 Mg/ha over roughly 1.2 billion ha of boreal forest is about 1.2 Pg of biomass (~0.6 Pg C). So "the difference is small" per pixel can still matter for the carbon budget. Pixel-level random error mostly averages out in a total, but systematic differences don't. For stock, **bias by AGBD range, weighted by the area in each range**, matters more than RMSD.

**Offsetting changes hide in the mean.** If the multi-year model raises high-biomass stands and lowers sparse ones, the mean difference can be near zero while the distribution, and any change estimates built on it, differ a lot.

**What I'd add:**

1. **Where the maps differ, by AGBD range.** I'd show the multi − single difference by AGBD interval: its mean, its spread, and the area share of each interval.
   - **Binning pitfall:** binning by either map's own value builds in a regression-to-the-mean artifact, so it would show apparent differences that aren't real. Instead I'd bin by the average of the two maps, or by something independent such as stand age or land cover.

2. **Whether each change moves toward the field value, by AGBD range.** At each plot, switching from single-year to multi-year falls into one of four classes:

   | | Moved toward the field value | Moved away from it |
   |---|---|---|
   | **Estimate went up** | fixed an underestimate | made it an overestimate |
   | **Estimate went down** | fixed an overestimate | made it an underestimate |

   I'd tabulate these by field AGBD interval (0–25, 25–50, 50–100, 100–150, >150 Mg/ha). This is the clearest answer to "does it improve estimates, in which direction, and where". For example, it would show whether multi-year mostly fixes underestimation in tall, dense forest.

3. **Total stock for each run, and where the difference comes from.**
   - **Totals:** the domain total (Pg) for each 2020 map, with a confidence interval, and the difference.
   - **Breakdown:** how much of the difference comes from each AGBD interval and latitude band. A waterfall-style chart works well here.
   - **Source:** if each tile has a stats file (your older notebooks read `*_stats.Rds` per tile, and the stability notebook uses per-tile `*boreal.csv` totals), the totals can come from those without reading every pixel. Otherwise I'd sum the maps over the sampled tiles and scale up.

4. **Which total is more plausible.** The field plots aren't a probability sample, so they can't give an unbiased domain total. What they can give is the bias per AGBD interval for each map. Applying that bias to the area in each interval shows how far each map's total would shift if those biases held everywhere. That's indicative, not a corrected estimate, and I'd label it that way.

#### Questions before I change anything

1. **Per-tile totals for the single-year 2020 run:** does its DPS output have the per-tile stats files (`*_stats.Rds` or `*boreal.csv`), as the multi-year run does? If so, the stock comparison is cheap and covers every tile.
2. **Domain for the totals:** biome 8 (boreal) only, or the full circumpolar mapping domain? Your stability notebook has a TODO about exactly this.
3. **A DPS run for option A:** is a single-year run for one or two poor ICESat-2 years on ~100 tiles feasible? And which years do you consider worst? From that one tile, 2021 and 2023 look thin, but it may differ by region.
4. **New notebook or extend this one:** add these as new sections here, or make a companion "effect on stock" notebook? I'd lean towards extending this one, with the stock result added to the scorecard.

---

## 2026-10-12: Answers and decisions

### Answers (Paul Montesano)

1. No `*_stats.Rds`; each tile has `ensemble_stats.csv` and `boreal.csv`.
2. Boreal (biome 8) only.
3. Single-year runs are easy: hundreds of tiles per year, 2016–2025. Provide a tile list, then compare using more single-year results.
4. Extend this notebook.

Also: on MAAP Hub, `/home/jovyan` replaces `/projects`.

### Decisions and notes

- **Biome code.** In the WWF terrestrial ecoregions used by `stability_boreal_v3.1_multiyear.ipynb` (`ecoregion_biome_dict`), biome **6** is "Boreal Forests/Taiga" and biome **8** is "Temperate Grasslands, Savannas & Shrublands". The notebook uses a `BOREAL_BIOME` setting that defaults to 6. *To confirm.*
- **Single-year years.** ICESat-2 launched in September 2018, so there are no growing-season ATL08 observations for 2016–2018. Single-year models are possible only for 2019–2025. Being able to map 2016–2018 at all, from 2019–2024 ICESat-2 paired with each year's HLS, is itself an advantage of the multi-year model. It is stated in the notebook.
- **Settings for the new single-year runs.** To remove the confounds in the 2020 comparison (`niter`, run date, code commit), run the new single-year models with the same `mapBoreal` version and settings as the multi-year runs (v3.1.0, `niter = 30`, ATL08 v6). Change only the ICESat-2 training years.
- **Tile list.** The tile list for the single-year runs includes every tile containing a validation field plot, so §4 can be repeated for each year, plus a stratified sample (realm × latitude band) of boreal-biome tiles for the training, map and stock sections.
- **Stock totals** come from each tile's `*boreal_eco.csv` (AGB_Pg per iteration per ecoregion), filtered to the boreal biome, for tiles present in both runs.

### Changes made (notebook v2)

| Section | Change |
|---|---|
| §0 Settings | `SINGLE_TINDEX`: one single-year tile index per year; every section runs for each year listed. `PROJ` resolves to `/projects` (MAAP ADE) or `/home/jovyan` (MAAP Hub). `BOREAL_BIOME` (default 6). |
| §2 Training data | Per tile **and year**. New **A0**: obs a single-year model would have had, per ICESat-2 year and latitude band, from the dated obs in the multi-year pool. |
| §3 Map differences | New **B4–B5**: multi − single by AGBD range (bins on the mean of the two maps, boreal-biome pixels), and each range's contribution to the overall difference. |
| §4 Field plots | Per year and pooled. New **C4**: direction of change (raised/lowered × closer/further) by field AGBD range, with the net change in \|error\|. |
| §5 Stability | Uses single-year AGBD series once ≥ 4 single-year years exist; height (v3.0 vs v3.1) until then. |
| §6 Boreal stock (new) | Totals per run and year on the same tiles, from `*boreal_eco.csv` (or the stability notebook's `boreal_eco_all_years_df.csv`), boreal-biome ecoregions only; difference scaled to the full multi-year boreal total where only some tiles have a single-year run; breakdown by continent × latitude; error in each total implied by field-plot biases per map-AGBD range (indicative). |
| §7 Scorecard | Per-year RMSD rows, stock rows. Verdict states the stock effect. |

### Tile list for the single-year runs

`../tiles/single_year_run_tiles.csv` (497 tiles; `.txt` has tile numbers only; map in `.png`), made by `../tiles/make_single_year_run_tiles.R` from `boreal_tiles_v004.gpkg`, the WWF circumboreal boundary, and the four field-plot sources:

| reason | tiles | used in |
|---|---|---|
| field plots (tiles with ≥ 1 plot and ≥ 25 % boreal) | 381 | §4 accuracy per year, §5 stability |
| stratified sample (≥ 50 % boreal; 10 per realm × 5° latitude band) | 110 | §2 training, §3 map differences, §6 stock scaling |
| earlier examples (from the first comparison notebook) | 6 | §2–3 |

**Years to run:** 2019–2025 (no ICESat-2 growing season before 2019). If capacity is limited, start with contrasting years: thin ICESat-2 years (e.g. 2021, 2023) and full years (e.g. 2022, 2024).
