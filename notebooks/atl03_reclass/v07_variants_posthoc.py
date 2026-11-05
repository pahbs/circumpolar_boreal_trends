"""v0.7 variants computed from the saved v0.7 segment tables (no rerun; LOG 19 Oct 2026).

Rule (b) of v0.7 (`presence.absent_sigma`) only turns v0.6 zeros into no-height (`veg_uncertain`); everything else in
v0.7 is unchanged. So each variant below is exact from the v0.7 tables (checked: uncertain == v0.6 zero -> v0.7 NaN, 1,334
CanElevation and 6,978 LVIS segments):
  v0.7a   rule (a) night RH100 only: uncertain segments back to 0 m (= v0.7 config without absent_sigma)
  v0.7n   rule (b) only where sun >= 5 deg is NOT applied (uncertain -> 0 m by day). Below 5 deg the expected background in
          the 5 m layer is < 0.5 photons (G-LiHT tables: 18,806 of 18,822 segments), so in the training pool v0.7n == v0.7.
  hyb     control height (ATL08 photon classes, our binning) everywhere; 0 m where v0.7 finds vegetation absent (<= 1 sigma)
  hyb_a   same, with v0.6's zeros (<= 3 sigma, = v0.7a zeros)
Outputs: runs/v0.7/variants/*.csv
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))
import geopandas as gpd
import icesat2_photon_lib as ipl, validation_lib as val, presentation_lib as pl

cfg = ipl.load_config(REPO / "config" / "atl03_reclass_v0.7.yaml")
WORK = Path(cfg["paths"]["work_dir"]); OUT = WORK / "runs" / "v0.7" / "variants"; OUT.mkdir(exist_ok=True)
NEW = ["v0.7a", "v0.7n", "hyb", "hyb_a"]
DAY_SUN = 5.0


def add_variants(a):
    if "h_canopy_v07" in a:                                  # notebooks 09 / 10: one column per version
        h = a["h_canopy_v07"]
        b = lambda c: a[c + "_v07"].fillna(False).astype(bool)
        unc = h.isna() & ~b("low_signal") & ~b("veg_unmeasured") & ~b("veg_present") & b("veg_detectable")
        zero = b("short_veg")
    elif "h_canopy" in a and "veg_uncertain" in a:          # notebooks 01 / 05: v0.7 only
        h = a["h_canopy"]
        unc = a["veg_uncertain"].fillna(False).astype(bool)
        zero = a["short_veg_flag"].fillna(False).astype(bool)
    else:
        return a
    a = a.copy()
    a["h_canopy_v07a"] = h.mask(unc, 0.0)
    a["h_canopy_v07n"] = h.mask(unc & (a.solar_elevation >= DAY_SUN), 0.0)
    a["h_canopy_hyb"] = a.h_canopy_atl08.mask(zero, 0.0)
    a["h_canopy_hyb_a"] = a.h_canopy_atl08.mask(zero | unc, 0.0)
    return a


_rp = gpd.read_parquet
gpd.read_parquet = lambda f, *k, **kw: add_variants(_rp(f, *k, **kw)) if "/runs/v0.7/" in str(f) else _rp(f, *k, **kw)
pl.VERSIONS = pl.VERSIONS + NEW
d_all = pl.load_all(WORK)
d = d_all[d_all.disturbance.isin(["none", "after"])].copy()
ce = d.reference == "CanElevation lidar"
d = pd.concat([d, d[ce & ~d.region.isin(pl.CE_WEST)].assign(reference="CanElevation east (seen)")], ignore_index=True)
REFS = pl.REFS[:2] + ["CanElevation east (seen)"] + pl.REFS[2:]

# 1. training pool (strong, sun < 5 deg): same segments for all, track bootstrap
V = [pl.TODAY, pl.CONTROL, "v0.6", "v0.7", "v0.7a", "hyb", "hyb_a"]
c = pl.training_cohort(d)
CS = pl.cohort_summary(c, V, n_boot=300)
CS.to_csv(OUT / "cohort_summary_variants.csv", index=False)

# 2. the height gradient, training pool: each version on its own segments (coverage = share of cohort segments with a height)
EDGES = [0, 1, 2, 5, 10, 15, 20, 25, 60]
c["hc"] = pd.cut(c.ref_h, EDGES, right=False, labels=val.height_class_labels(EDGES))
rows = []
for (ref, hc), g in c.groupby(["reference", "hc"], observed=True):
    for v in V:
        f = g[g[v].notna()]; e = f[v] - f.ref_h
        rows.append({"reference": ref, "height_class": hc, "version": v, "n_class": len(g), "n": len(f), "coverage": len(f) / len(g),
                     "bias": e.mean(), "rmse": np.sqrt((e ** 2).mean()), "mae": e.abs().mean(), "zero_share": (f[v] == 0).mean()})
G = pd.DataFrame(rows); G.to_csv(OUT / "cohort_gradient_variants.csv", index=False)

# 3. all observations (any beam, any sun): what rule (b) does by day
VA = [pl.TODAY, "v0.6", "v0.7", "v0.7n", "v0.7a"]
rows = []
for ref in REFS:
    g = d[d.reference == ref]
    for v in VA:
        f = g[g[v].notna()]
        rows.append({"reference": ref, "version": v, "coverage": g[v].notna().mean(),
                     "correct_zeros_lt1m": int(((f.ref_h < 1) & (f[v] == 0)).sum()), "zeros_over_forest_ge5m": int(((f.ref_h >= 5) & (f[v] == 0)).sum()),
                     "r2_own": val.r_squared(f[v], f.ref_h), "rmse_own": np.sqrt(((f[v] - f.ref_h) ** 2).mean())})
A = pd.DataFrame(rows); A.to_csv(OUT / "all_obs_zero_rule.csv", index=False)
print("done", OUT)
