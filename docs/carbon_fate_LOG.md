# Circumpolar boreal carbon fate: discussion log

Running notes on what the v3.1 AGBD time series (2016–2025) says about the recent fate of aboveground boreal forest carbon. Newest entry first.

## Current status

- **Main conclusion so far:** the mapped boreal AGB stock shows no decline over 2016–2025. Eurasia is increasing (about +0.26 Pg biomass/yr, p ≈ 0.07). North America is flat, with gains and losses roughly cancelling.
- **The 2019 "spike" is a dip,** about −4 Pg (−5%) in one year across both continents. It is almost certainly an input artifact, not real carbon loss (see 2026-10-16).
- **The stock level is uncertain.** Field plots suggest the maps underestimate the total by about 30% (indicative). The size of the trend is uncertain too: the 2019 artifact alone is about 15× the annual Eurasian gain.
- **Next:** diagnose 2019, compute robust trends with and without 2019 and 2016–2018, run the landscape analysis on all landscapes, and fix the bugs in the landscape summary (plan below).

---

## 2026-10-16: First synthesis (stability, landscapes, age trends, validation, model strategy)

### Sources read
- `icesat2_boreal/notebooks/stability_boreal_v3.1_multiyear.ipynb`: per-tile `boreal.csv`/`boreal_eco.csv`, 30 model iterations, summed to tile, realm, biome and ecoregion.
- `carbon_fate.ipynb`, `landscape_biomass_change.ipynb`, `compare_age_trends_landscapes_new_edits.ipynb`: HydroBASINS level-8 landscapes × 2020 age cohort × Kendall trend class, AGB in 2020 vs 2025.
- `carbon_accumulation_meta_smry.ipynb`: summary tables only. It does not yet give C totals per age cohort × ecoregion (its own TODO).
- `validation/validation_v3.1_height_agbd.ipynb`: real field-plot results.
- `model_strategy_single_vs_multi_yr.ipynb` and its LOG: single-year vs multi-year training, and the effect on stock.

### The time series as it stands (multi-year model, `full_run_niter30_multiyear_atl08v6`)
- Mapping domain total is about 78–81 Pg AGB (roughly 39–40 Pg C), from 1975 Eurasian and 1029 North American tiles. The tile count is the same in every year.
- Linear trend 2016–2025:
  - Domain: +264 Tg/yr (R² 0.28).
  - Boreal biome, Eurasia: +213 Tg/yr (p 0.069).
  - Boreal biome, North America: +7.5 Tg/yr (p 0.78).
- Largest increasing boreal ecoregions:
  - East Siberian taiga: +82 Tg/yr (R² 0.33)
  - Scandinavian & Russian taiga: +27 Tg/yr (R² 0.06)
  - Okhotsk-Manchurian taiga: +17 Tg/yr (R² 0.31)
  - In North America, the trends are small and noisy: Northern Cordillera +4.6, Interior AK-Yukon lowland +5.1, Eastern Canadian forests +3.7 Tg/yr.
- No boreal ecoregion trend is significant at p < 0.05. The series has only 10 points, and one of them (2019) is an outlier.

### What the validation does to that picture
- **Field plots, boreal domain pooled:**
  - AGBD: bias −18 Mg/ha (−32%; CI −26 to −11), RMSD 53, r² 0.43, slope 0.37.
  - Height: bias −2.4 m, r² 0.47, slope 0.68.
  - By source: NFI AGBD bias −31 Mg/ha. Kolyma (low biomass) +6.7 Mg/ha.
  - So the map is compressed: high biomass is underestimated and low biomass overestimated.
- **Implied bias in the total** (field-plot error by map AGBD range, weighted by map area): −29 to −34% for the multi-year model, −23 to −29% for the single-year model. If this held everywhere, the true stock would be about 1.4× the mapped stock. This is *indicative*: the plots are not a probability sample, and many plots predate the maps.
- **Effect on trends:** a constant bias cancels in a trend. Compression does not. With a slope of 0.37, real gains or losses in high-biomass stands are probably understated, and gains in sparse, low-stature stands may be overstated. The ATL03 v0.3 work shows the same low-end problem in the training data: ATL08 overestimates short vegetation.
- **Stand age:** the age map vs NFI gives Spearman 0.22, r² 0.14, RMSD 69 yr. Age-cohort splits should be read as broad classes only.
- **Single-year vs multi-year model:**
  - On the same ~430 tiles, single-year totals swing by ±1 Pg (about 10%) from year to year. Multi-year totals vary by less than 0.3 Pg.
  - Single minus multi is −5% to +8% depending on the year.
  - So the multi-year series is the right one for trends. Its smoothness is partly by construction, because all years share one training pool. The LVIS 2017→2019 change test is the check that real change is still detected.

### Why 2019 looks anomalous
- It is a **dip**: about 80.0 Pg in 2018, 75.9 Pg in 2019, 78.3 Pg in 2020. Fifteen ecoregions on both continents are flagged more than 2 SD low. For example, East Siberian taiga drops about 1.2 Pg and Scandinavian & Russian taiga about 1 Pg, then both recover in 2020–2021.
- **Why it is not real:** a 5% loss of standing biomass in one year, followed by recovery, is not ecologically plausible at this scale. Biomass does not regrow in one year. The dip also appears in **Biome 98 (lakes/water)**, which drops 7% in 2019, where no vegetation change can happen.
- **What it cannot be:**
  - Tile count: 1975 + 1029 tiles in every year.
  - ICESat-2 training: the multi-year model uses the same 2019–2024 pool for every map year.
- **That leaves the 2019 HLS covariates,** the only year-specific input. Candidate causes:
  - Composite timing or day-of-year mix in 2019.
  - Haze and smoke contamination: 2019 had extreme Siberian and Alaskan fire seasons, but that would not explain Scandinavia.
  - A change in HLS processing or version for 2019 granules.
  - Gap-fill differences.
- **Side effect on trends:** a low point early in the series inflates OLS slopes. Part of the "increasing" signal may come from 2019 being low.

### Ecoregion vs landscape approaches

| | Ecoregion (WWF) totals | Landscape (HydroBASINS L8) × age × trend class |
|---|---|---|
| **Strengths** | Complete coverage, all 10 years, iteration uncertainty, directly comparable to inventories and literature; good at exposing systematic artifacts (2019). | Units close to process scale; splits net change into gross gains and losses by cohort; links to C accumulation and age; shows *where* in the age structure carbon moves. |
| **Weaknesses** | Net only: fire losses and regrowth gains cancel inside huge units. A few very large ecoregions dominate. Tile-edge fragments give tiny, meaningless series. OLS on 10 points. Uncertainty covers model iterations only. | So far a test subset only (1,541 boreal landscapes in the latest figure; one run read 8 of the expected CSVs, and its GPKGs were missing). Uses endpoints (2020 vs 2025), which are sensitive to single-year noise. Trend classes come from the same AGB series, so "increase gains, decline loses" is circular; only the balance and the location carry information. Weak age map. Known bugs: `change_percent` sum marked "# wrong", `n_pixels` not joined, SDs summed instead of combined. |

**Landscape test result (2020→2025, boreal biome landscapes):**
- Strong-decline landscapes: about −14 Tg. Strong-increase landscapes: about +15 Tg. Stable: about +10 Tg. Net positive.
- The **mature** cohort carries most of both the gains and the losses. Young and non-forest cohorts carry little.
- If this holds at full scale, the near-term fate of boreal AGB is set by gains and losses in mature forest, not by young-forest regrowth. That matters for comparison with Yang et al. (2023).

### What we can conclude now, with caveats
1. **No boreal-wide AGB decline 2016–2025.** This is robust to a constant map bias and to the 2019 artifact, which pulls only one point.
2. **Net gains are mostly in Eurasia,** led by East Siberian taiga. North America is near zero net, consistent with fire losses offsetting growth. The direction is moderately robust. The size (about +0.1 Pg C/yr) is uncertain: of the same order as the interannual artifacts, and possibly understated because the map is compressed.
3. **The stock level is the weakest number:** mapped about 39–40 Pg C, and field plots suggest about 30% higher (indicative).
4. **Mature forests control the balance** in the landscape test. Treat this as preliminary until the full run is done.

### Plan for additional analysis (priority order)
1. **Diagnose 2019** (cheap, decisive):
   - Map the per-tile ratio AGB₂₀₁₉ / mean(AGB₂₀₁₈, AGB₂₀₂₀).
   - Correlate it with the HLS composite DOY/year layers (`get_juliandate_year_hls` in compute_trends), the observation count and the band medians.
   - Test it over water and rock pixels.
   - Check the HLS version and composite settings used for 2019.
2. **Robust trends:**
   - Theil-Sen with Mann-Kendall, with and without 2019.
   - Also for 2019/2020–2025 only, because 2016–2018 are HLS-only years extrapolated from the 2019–2024 ICESat-2 pool.
   - Check for a step change when Landsat 9 enters HLS (2022), which changes composite density.
3. **Bias-aware totals:** apply the validation's bias by map AGBD range to each year. Report mapped and adjusted totals side by side, labelled indicative.
4. **Full landscape run:**
   - Run on all landscapes.
   - Fix `change_percent` and the `n_pixels` join, and combine SDs properly.
   - Use slope-based change instead of 2020/2025 endpoints.
   - Attribute losses with fire perimeters and forest loss products instead of the circular trend classes.
5. **Uncertainty budget per region:** model-iteration spread + systematic bias + an interannual artifact term (the residual SD around the trend).
6. **LVIS 2017→2019 change test**, to confirm that the multi-year model detects real change.
7. **After ATL03 v0.4 (the zero rule):** check how the corrected low-stature training data change the low-AGBD end of the maps and the North American trends.
