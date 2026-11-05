"""Sanity check of night RH100 on the control and the hybrid (LOG 19 Oct 2026); needs v07_control_night_top.py build.

Versions compared on the undisturbed training pool (strong beams, sun < 5 deg), each on its own segments:
  control (RH98) vs ctl100 (night RH100); hyb vs hyb100 (= ctl100, 0 m where v0.7 finds vegetation absent);
  v0.6 vs v0.7 = what rule (a) did for our own classes (v0.7 also has rule b; heights > 0 m differ only by rule a).
Checks: (1) the rebuilt control RH98 reproduces the stored h_canopy_atl08 (exact except G-LiHT: 79 %, same photons,
relief differs by a few cm; so RH100 is compared with the rebuilt RH98, `ctl98chk`); (2) how much RH100 lifts the top, by height;
(3) overestimates (ICESat-2 > reference + 5 m) and implausible heights (> 35 m), above all over short vegetation;
(4) bias / MAE / r² by height class; (5) the worst cases. Outputs: runs/v0.7/variants/night_top_check_*.csv
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))
import geopandas as gpd
import icesat2_photon_lib as ipl, validation_lib as val, presentation_lib as pl

cfg = ipl.load_config(REPO / "config" / "atl03_reclass_v0.7.yaml")
WORK = Path(cfg["paths"]["work_dir"]); OUT = WORK / "runs" / "v0.7" / "variants"
CTL = {r: pd.read_parquet(OUT / f"control_night_top_{r}.parquet") for r in ("glihit", "seward", "canelevation", "lvis")}
K = ["file", "track_id", "seg"]
COLS = ["h_canopy_ctl98", "h_canopy_ctl100", "ctl_night_top", "n_canopy_ctl"]


def inject(a, f):
    f = Path(f)
    if "/runs/v0.7/" not in str(f):
        return a
    if f.name == "segments_canelevation.parquet":
        a = a.assign(file=a.box_id); c = CTL["canelevation"]; zero = a.short_veg_v07
    elif f.name == "segments_lvis.parquet":
        a = a.assign(file=a.lvis_stem); c = CTL["lvis"]; zero = a.short_veg_v07
    elif f.name.endswith("_segments_als.parquet"):
        a = a.assign(file=f.name.split("_segments")[0]); c = CTL["glihit"]; zero = a.short_veg_flag
    elif f.name.endswith("_segments.parquet") and f.parent.name == "seward":
        a = a.assign(file=f.stem.replace("_segments", "_photons")); c = CTL["seward"]; zero = a.short_veg_flag
    else:
        return a
    zero = zero.fillna(False).astype(bool).to_numpy()
    a = a.merge(c[K + COLS].drop_duplicates(K), on=K, how="left")
    a["h_canopy_hyb"] = a.h_canopy_ctl98.mask(zero, 0.0)          # rebuilt RH98: same pass as RH100
    a["h_canopy_hyb100"] = a.h_canopy_ctl100.mask(zero, 0.0)
    a["h_canopy_ctl98chk"] = a.h_canopy_ctl98
    return a


_rp = gpd.read_parquet
gpd.read_parquet = lambda f, *k, **kw: inject(_rp(f, *k, **kw), f)
pl.VERSIONS = pl.VERSIONS + ["ctl100", "hyb", "hyb100", "ctl98chk"]
d = pl.load_all(WORK)
d = d[d.disturbance.isin(["none", "after"])]
d = pd.concat([d, d[(d.reference == "CanElevation lidar") & ~d.region.isin(pl.CE_WEST)].assign(reference="CanElevation east (seen)")],
              ignore_index=True)
c = pl.training_cohort(d)

# (1) reproduction of the stored control
rep = c.groupby("reference").apply(lambda g: pd.Series({
    "n": len(g), "stored_has_h": g[pl.CONTROL].notna().sum(), "rebuilt_has_h": g.ctl98chk.notna().sum(),
    "equal_within_1cm": (np.abs(g.ctl98chk - g[pl.CONTROL]) < 0.01).sum(), "both_nan": (g.ctl98chk.isna() & g[pl.CONTROL].isna()).sum()}))
rep.to_csv(OUT / "night_top_check_reproduction.csv"); print(rep, "\n")

EDGES = [0, 1, 2, 5, 10, 15, 20, 25, 60]
c["hc"] = pd.cut(c.ref_h, EDGES, right=False, labels=val.height_class_labels(EDGES))
PAIRS = [("ctl98chk", "ctl100"), ("hyb", "hyb100"), ("v0.6", "v0.7")]

# (2) lift of the top, (3)-(4) errors by height class
rows = []
for (ref, hc), g in c.groupby(["reference", "hc"], observed=True):
    for v in [x for p in PAIRS for x in p]:
        f = g[g[v].notna()]; e = f[v] - f.ref_h
        rows.append({"reference": ref, "height_class": hc, "version": v, "n": len(f), "bias": e.mean(), "mae": e.abs().mean(),
                     "rmse": np.sqrt((e ** 2).mean()), "over_5m": (e > 5).mean(), "over_10m": (e > 10).mean(),
                     "gt_35m": int((f[v] > 35).sum())})
    for a, b in PAIRS:
        f = g[g[a].notna() & g[b].notna() & (g[a] > 0)]
        lift = f[b] - f[a]
        rows.append({"reference": ref, "height_class": hc, "version": f"lift {b}-{a}", "n": len(f), "lift_share": (lift > 0.01).mean(),
                     "lift_median": lift[lift > 0.01].median(), "lift_p95": lift.quantile(0.95), "lift_max": lift.max()})
T = pd.DataFrame(rows); T.to_csv(OUT / "night_top_check_by_class.csv", index=False)

# overall, same segments for the pair
rows = []
for ref, g in c.groupby("reference"):
    for a, b in PAIRS:
        f = g.dropna(subset=[a, b])
        for v in (a, b):
            e = f[v] - f.ref_h; fo = f[f.ref_h >= 5]; eo = fo[v] - fo.ref_h
            rows.append({"reference": ref, "pair": f"{a} vs {b}", "version": v, "n": len(f), "r2": val.r_squared(f[v], f.ref_h),
                         "bias": e.mean(), "mae": e.abs().mean(), "r2_forest": val.r_squared(fo[v], fo.ref_h), "bias_forest": eo.mean(),
                         "mae_forest": eo.abs().mean(), "over_5m_lt5m_ref": ((f.ref_h < 5) & (e > 5)).sum() / max(1, (f.ref_h < 5).sum()),
                         "gt_35m": int((f[v] > 35).sum())})
S = pd.DataFrame(rows); S.to_csv(OUT / "night_top_check_summary.csv", index=False)

# (5) worst cases: largest new overestimates from ctl100
w = c[c.ctl100.notna() & c.ctl98chk.notna()].assign(err98=lambda x: x.ctl98chk - x.ref_h, err100=lambda x: x.ctl100 - x.ref_h,
                                                   lift=lambda x: x.ctl100 - x.ctl98chk)
w = w[w.reference != "CanElevation east (seen)"].sort_values("err100", ascending=False).head(25)
w[["reference", "region", "track", "lon", "lat", "solar_elevation", "ref_h", pl.TODAY, "ctl98chk", "ctl100", "v0.7", "lift", "err100",
   "slope_deg"]].to_csv(OUT / "night_top_check_worst.csv", index=False)
print("done")
