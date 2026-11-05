"""Re-score every version on the production training pool (LOG 19 Oct 2026): the segments that pass
icesat2_boreal FilterUtils.filter_atl08_qual_v5, the filter process_atl08_boreal.py applies to our training data.

The filter runs, unchanged and imported from icesat2_boreal, on the SlideRule PhoREAL (today) segments, prepared as in
process_atl08_boreal.py (y / m / doy from the time stamp). A validation segment is in the pool if its PhoREAL segment
(nearest on the same track within 20 m: the match that gave h_canopy_phoreal) passes. Same mask for every version, as in
production (land-cover cap on today's ATL08 height); each version's own heights above that cap are counted apart. Segments
with no PhoREAL file (Seward council_01, CanElevation boxes without one) cannot be filtered and drop out. Then undisturbed
stands only (no Hansen loss before ICESat-2), as in notebook 11.

Versions: today, control, v0.6, v0.7, and from the v0.7 tables (exact; v07_variants_posthoc.py):
  v0.7a  v0.7 without rule (b) (uncertain -> 0 m)
  hyb    control RH98 (rebuilt, v07_control_night_top.py), 0 m where v0.7 finds vegetation absent (<= 1 sigma)
  hyb_a  same with v0.6's zeros
  hyb100 hyb with night RH100 (v0.7 rule a) on the control heights
Run on a forest node:  python v07_rescore_filtered.py [n_boot]
Outputs: runs/v0.7/filtered/*.csv
"""
import contextlib, io, sys
from pathlib import Path
import numpy as np, pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))
sys.path.insert(0, str(Path.home() / "code" / "icesat2_boreal" / "lib"))
import geopandas as gpd
import icesat2_photon_lib as ipl, validation_lib as val, presentation_lib as pl
from FilterUtils import filter_atl08_qual_v5

cfg = ipl.load_config(REPO / "config" / "atl03_reclass_v0.7.yaml")
WORK = Path(cfg["paths"]["work_dir"]); RUN = WORK / "runs" / "v0.7"; OUT = RUN / "filtered"; OUT.mkdir(exist_ok=True)
N_BOOT = int(sys.argv[1]) if len(sys.argv) > 1 else 300
LC_CAP = dict(zip([0, 111, 113, 112, 114, 115, 116, 121, 123, 122, 124, 125, 126, 20, 30, 90, 100, 60, 40, 50, 70, 80, 200],
                  [0, 60, 60, 60, 60, 60, 60, 50, 50, 50, 50, 50, 50, 20, 10, 10, 5, 5, 0, 0, 0, 0, 0]))   # filter_atl08_qual_v5 defaults
_rp = gpd.read_parquet
FUNNEL = []


def phoreal_pass(f, ref):
    """PhoREAL segments of one file with pass = survives filter_atl08_qual_v5, and the segment's land cover."""
    pr = _rp(f).to_crs(4326).reset_index(drop=True)
    if not len(pr):
        return pr
    t = pd.to_datetime(pr["time_ns"])
    a = pr.assign(y=t.dt.year, m=t.dt.month, doy=t.dt.dayofyear, _rid=np.arange(len(pr)))
    with contextlib.redirect_stdout(io.StringIO()):
        kept, meta = filter_atl08_qual_v5(a.copy(), RETURN_METADATA=True)
    FUNNEL.append(meta.assign(reference=ref, file=f.stem))
    return pr.assign(filt_pass=pr.index.isin(kept["_rid"]), lc=pr["segment_landcover"])


def add_filter(a, prf, ref):
    if prf is None or not Path(prf).exists():
        return a.assign(h_canopy_filt=np.nan, lc_filt=np.nan)
    pr = phoreal_pass(Path(prf), ref)
    g = gpd.GeoDataFrame(a, geometry="geometry", crs=4326) if not isinstance(a, gpd.GeoDataFrame) else a
    m = ipl.match_segments(g[["track_id", "geometry"]].assign(_k=np.arange(len(g))), pr[["track_id", "geometry", "filt_pass", "lc"]],
                           ["filt_pass", "lc"], suffix="_m").sort_values("_k")
    if "filt_pass_m" not in m:                                # no track of this file has a PhoREAL segment
        return a.assign(h_canopy_filt=np.nan, lc_filt=np.nan)
    return a.assign(h_canopy_filt=np.where(m["filt_pass_m"].fillna(False).astype(bool).to_numpy(), 1.0, np.nan), lc_filt=m["lc_m"].to_numpy())


CTL = {r: pd.read_parquet(RUN / "variants" / f"control_night_top_{r}.parquet") for r in ("glihit", "seward", "canelevation", "lvis")}


def inject(a, f):
    f = Path(f)
    if "/runs/v0.7/" not in str(f):
        return a
    if f.name == "segments_canelevation.parquet":
        ref, key, sfx = "canelevation", a.box_id, "_v07"
        parts = [add_filter(g, WORK / "canelevation" / "photons" / f"{b}_phoreal.parquet", "CanElevation lidar") for b, g in a.groupby("box_id")]
    elif f.name == "segments_lvis.parquet":
        ref, key, sfx = "lvis", a.lvis_stem, "_v07"
        parts = [add_filter(g, WORK / "lvis" / "photons" / f"{s}_phoreal.parquet", "LVIS 2019") for s, g in a.groupby("lvis_stem")]
    elif f.name.endswith("_segments_als.parquet"):
        t = f.name.split("_segments")[0]
        ref, key, sfx = "glihit", pd.Series(t, index=a.index), ""
        parts = [add_filter(a, WORK / "glihit" / t / "phoreal.parquet", "G-LiHT lidar")]
    elif f.name.endswith("_segments.parquet") and f.parent.name == "seward":
        site = f.stem.replace("_segments", "")
        ref, key, sfx = "seward", pd.Series(f"{site}_photons", index=a.index), ""
        parts = [add_filter(a, WORK / "seward" / f"{site}_phoreal.parquet", "Seward UAV")]
    else:
        return a
    a = pd.concat(parts).loc[a.index] if len(parts) > 1 else parts[0]
    a = a.assign(file=key.loc[a.index] if ref in ("glihit", "seward") else (a.box_id if ref == "canelevation" else a.lvis_stem))
    # v0.7 variants (exact; v07_variants_posthoc.py)
    if sfx:
        h = a.h_canopy_v07; b = lambda c: a[c + sfx].fillna(False).astype(bool)
        unc = h.isna() & ~b("low_signal") & ~b("veg_unmeasured") & ~b("veg_present") & b("veg_detectable"); zero = b("short_veg")
    else:
        h = a.h_canopy; unc = a.veg_uncertain.fillna(False).astype(bool); zero = a.short_veg_flag.fillna(False).astype(bool)
    c = CTL[ref][["file", "track_id", "seg", "h_canopy_ctl98", "h_canopy_ctl100"]].drop_duplicates(["file", "track_id", "seg"])
    a = a.assign(_z=zero.to_numpy(), _u=unc.to_numpy(), h_canopy_v07a=h.mask(unc, 0.0).to_numpy())
    a = a.merge(c, on=["file", "track_id", "seg"], how="left")
    a["h_canopy_hyb"] = a.h_canopy_ctl98.mask(a._z, 0.0)
    a["h_canopy_hyb_a"] = a.h_canopy_ctl98.mask(a._z | a._u, 0.0)
    a["h_canopy_hyb100"] = a.h_canopy_ctl100.mask(a._z, 0.0)
    a["h_canopy_lcfilt"] = a.lc_filt
    return gpd.GeoDataFrame(a, geometry="geometry", crs=4326) if "geometry" in a else a


gpd.read_parquet = lambda f, *k, **kw: inject(_rp(f, *k, **kw), f)
V = [pl.TODAY, pl.CONTROL, "v0.6", "v0.7", "v0.7a", "hyb", "hyb_a", "hyb100"]
pl.VERSIONS = [pl.TODAY, "v0.2", "v0.3", "v0.4", "v0.5", "v0.6", "v0.7", "v0.7a", "hyb", "hyb_a", "hyb100", "filt", "lcfilt"]
d_all = pl.load_all(WORK)
pd.concat(FUNNEL).groupby("reference").sum(numeric_only=True).to_csv(OUT / "filter_funnel_phoreal.csv")

d = d_all[d_all.disturbance.isin(["none", "after"])].copy()
d = pd.concat([d, d[(d.reference == "CanElevation lidar") & ~d.region.isin(pl.CE_WEST)].assign(reference="CanElevation east (seen)")],
              ignore_index=True)
old = pl.training_cohort(d)                                   # 18 Oct pool: strong beams, sun < 5 deg
c = old[old.filt == 1].copy()                                 # production pool: + the rest of filter_atl08_qual_v5
cnt = pd.DataFrame({"pool_strong_sun5": old.groupby("reference").size(), "pool_filtered": c.groupby("reference").size(),
                    "no_phoreal_match": old[old["filt"].isna() & old[pl.TODAY].isna()].groupby("reference").size()})
cnt["kept_share"] = cnt.pool_filtered / cnt.pool_strong_sun5
cnt.to_csv(OUT / "pool_counts.csv"); print(cnt, "\n", flush=True)

# 1. summary on the same segments, track bootstrap
CS = pl.cohort_summary(c, V, n_boot=N_BOOT); CS.to_csv(OUT / "cohort_summary.csv", index=False)

# 2. the height gradient: each version on its own segments
EDGES = [0, 1, 2, 5, 10, 15, 20, 25, 60]
c["hc"] = pd.cut(c.ref_h, EDGES, right=False, labels=val.height_class_labels(EDGES))
cap = c.lcfilt.round().map(LC_CAP)
rows = []
for (ref, hc), g in c.groupby(["reference", "hc"], observed=True):
    for v in V:
        f = g[g[v].notna()]; e = f[v] - f.ref_h
        rows.append({"reference": ref, "height_class": hc, "version": v, "n_class": len(g), "n": len(f), "coverage": len(f) / len(g),
                     "bias": e.mean(), "rmse": np.sqrt((e ** 2).mean()), "mae": e.abs().mean(), "zero_share": (f[v] == 0).mean(),
                     "over_5m": (e > 5).mean(), "over_own_lc_cap": int((f[v] >= cap.loc[f.index]).sum())})
G = pd.DataFrame(rows); G.to_csv(OUT / "gradient.csv", index=False)

# 3. criteria C1-C4 and rarity-weighted retention (weights from today's pool samples per class)
rows = []
for ref, g in G[~G.reference.str.startswith("Seward")].groupby("reference"):
    t = g[g.version == pl.TODAY].set_index("height_class")
    w = 1 / (t.n / t.n.sum())
    for v, gv in g.groupby("version"):
        gi = gv.set_index("height_class"); fo = gi[gi.index.isin(["5-10 m", "10-15 m", "15-20 m", "20-25 m"])]
        tall = [k for k in gi.index if k in ("15-20 m", "20-25 m", "25+ m")]
        rows.append({"reference": ref, "version": v, "kept_rarity_weighted": (w * gi.n).sum() / (w * t.n).sum(),
                     "kept_unweighted": gi.n.sum() / t.n.sum(), "kept_ge15m": gi.n[tall].sum() / t.n[tall].sum(), "n_ge15m": int(gi.n[tall].sum()),
                     "min_class_cov_vs_today": (gi.coverage / t.coverage).min(), "worst_class": (gi.coverage / t.coverage).idxmin(),
                     "forest_zero_5_10": gi.loc["5-10 m", "zero_share"] if "5-10 m" in gi.index else np.nan,
                     "mae_forest_5_25": np.average(fo.mae, weights=fo.n), "bias_forest_5_25": np.average(fo.bias, weights=fo.n),
                     "bias_0_1": gi.loc["0-1 m", "bias"], "tall_weight_vs_0_1m": w[tall].mean() / w["0-1 m"]})
S = pd.DataFrame(rows).merge(CS[["reference", "version", "spurious_veg"]], on=["reference", "version"], how="left")
S.to_csv(OUT / "scorecard.csv", index=False)

# 4. forest >= 5 m by light (night / low sun), each version on its own segments
rows = []
for (ref, l), g in c[c.ref_h >= 5].groupby(["reference", "light2"]):
    for v in V:
        f = g[g[v].notna()]; e = f[v] - f.ref_h
        rows.append({"reference": ref, "light": l, "version": v, "n": len(f), "r2": val.r_squared(f[v], f.ref_h), "bias": e.mean(),
                     "rmse": np.sqrt((e ** 2).mean()), "mae": e.abs().mean(), "at_0m": (f[v] == 0).mean(),
                     "slope": np.polyfit(f.ref_h, f[v], 1)[0] if len(f) > 2 else np.nan})
pd.DataFrame(rows).to_csv(OUT / "forest_by_light.csv", index=False)
print("done", OUT)
