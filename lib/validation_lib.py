"""Validation metrics and standard plots for the ATL03 reclassification work."""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

CLASS_COLORS = {"noise": "#bdbdbd", "ground": "#a6611a", "canopy": "#1b9e77", "top": "#00441b",
                "buffer": "#fdb863", "none": "#ffffff", "unclassified": "#d7301f"}
ATL08_NAMES = {0: "noise", 1: "ground", 2: "canopy", 3: "top", 4: "unclassified"}
NEW_NAMES = {0: "noise", 1: "ground", 2: "canopy", 3: "top"}
# 30 m segment versions compared throughout (17 Oct 2026 names). All use the same ATL03 release 007 photons; a name
# says (1) whose photon classes and (2) who cut them into 30 m segments and computed the heights:
#   photon classes \ binning   SlideRule PhoREAL          our segment_metrics
#   ATL08 v007                 ATL08 · PhoREAL (today)    ATL08 · our binning (control)
#   reclassified (config v0.N) -                          reclassified v0.N
LABEL_CURRENT = "ATL08 · PhoREAL (today)"           # what our training files contain today
LABEL_CHECK = "ATL08 · our binning (control)"       # same ATL08 classes, our binning: separates binning from classification
LABEL_NEW = "reclassified"                          # + " v0.N" for a config version
SCHEME_COLORS = {LABEL_CURRENT: "#7570b3", LABEL_CHECK: "#d95f02", LABEL_NEW: "#1b9e77"}
# Photon classifications compared throughout:
PHOTON_ATL08 = "ATL08 v007 photon classes"
PHOTON_NEW = "reclassified photon classes"
PHOTON_REF = "reference photon labels"


def height_class_labels(edges):
    return [f"{a}-{b} m" if b < 60 else f"{a}+ m" for a, b in zip(edges[:-1], edges[1:])]


def r_squared(est, ref):
    """Squared Pearson correlation of estimate vs reference (finite pairs; NaN if < 3). Reported instead of r."""
    est, ref = np.asarray(est, float), np.asarray(ref, float)
    ok = np.isfinite(est) & np.isfinite(ref)
    if ok.sum() < 3 or np.std(est[ok]) == 0 or np.std(ref[ok]) == 0:
        return np.nan
    return float(np.corrcoef(est[ok], ref[ok])[0, 1] ** 2)


def zeros_by_height_class(est, ref, edges):
    """Per reference height class: n, share of estimates that are exactly 0 m, and bias / RMSE of the non-zero estimates.
    A 0 m height is right below ~1 m and wrong above ~2 m; mean bias alone rewards writing 0 m (LOG, 16 Oct 2026)."""
    est, ref = np.asarray(est, float), np.asarray(ref, float)
    ok = np.isfinite(est) & np.isfinite(ref)
    cls = pd.cut(ref[ok], edges, right=False, labels=height_class_labels(edges))
    d = pd.DataFrame({"cls": cls, "est": est[ok], "e": est[ok] - ref[ok]})
    rows = {}
    for c, g in d.groupby("cls", observed=False):
        nz = g[g.est > 0]
        rows[c] = {"n": len(g), "zero_share": (g.est == 0).mean() if len(g) else np.nan,
                   "bias_nonzero": nz.e.mean(), "rmse_nonzero": np.sqrt((nz.e ** 2).mean()), "n_nonzero": len(nz)}
    return pd.DataFrame(rows).T


def metrics_by_height_class(est, ref, edges, spurious=None):
    """Bias, RMSE, MAE, n by reference height class; optional spurious-vegetation rate."""
    est, ref = np.asarray(est, float), np.asarray(ref, float)
    ok = np.isfinite(est) & np.isfinite(ref)
    est, ref = est[ok], ref[ok]
    cls = pd.cut(ref, edges, right=False, labels=height_class_labels(edges))
    d = pd.DataFrame({"cls": cls, "err": est - ref, "est": est, "ref": ref})
    out = d.groupby("cls", observed=False).agg(n=("err", "size"), bias=("err", "mean"),
                                               rmse=("err", lambda e: np.sqrt(np.mean(e ** 2)) if len(e) else np.nan),
                                               mae=("err", lambda e: np.mean(np.abs(e)) if len(e) else np.nan),
                                               ref_mean=("ref", "mean"), est_mean=("est", "mean"))
    allrow = pd.DataFrame({"n": [len(d)], "bias": [d["err"].mean()], "rmse": [np.sqrt(np.mean(d["err"] ** 2))],
                           "mae": [np.mean(np.abs(d["err"]))], "ref_mean": [ref.mean()], "est_mean": [est.mean()]},
                          index=["all"])
    out = pd.concat([out, allrow])
    if spurious:
        low = ref < spurious["ref_below_m"]
        out.loc["spurious_veg_rate", "n"] = int(low.sum())
        out.loc["spurious_veg_rate", "bias"] = float((est[low] > spurious["est_above_m"]).mean()) if low.any() else np.nan
    return out


def confusion(ref_label, est_class, names):
    """Row-normalised confusion matrix of reference labels (rows) vs estimated classes (columns)."""
    # positional pairing: both inputs as plain arrays (index alignment would mismatch photons)
    ref_arr = np.asarray(ref_label)
    est = pd.Series(np.asarray(est_class)).map(names).fillna("other").to_numpy()
    t = pd.crosstab(pd.Series(ref_arr, name="reference"), pd.Series(est, name="estimated"))
    return t, t.div(t.sum(axis=1), axis=0)


def plot_profile(ax, p, class_col, names, relief_col=None, ref=True, title="", s=4):
    """Photon heights along track coloured by class, with reference ground and canopy top if present."""
    x = p["x_atc"] - p["x_atc"].min()
    y = p[relief_col] if relief_col else p["height"]
    for k, nm in names.items():
        m = p[class_col] == k
        if m.any():
            ax.scatter(x[m], y[m], s=s, c=CLASS_COLORS.get(nm, "k"), label=nm, lw=0, alpha=0.8, zorder=2)
    if ref and "ref_ground" in p and not relief_col:
        o = np.argsort(x.to_numpy())
        ax.plot(x.to_numpy()[o], p["ref_ground"].to_numpy()[o], c="k", lw=0.8, label="reference ground", zorder=3)
        ax.plot(x.to_numpy()[o], p["ref_top"].to_numpy()[o], c="k", lw=0.8, ls="--", label="reference canopy top", zorder=3)
    ax.set_title(title, fontsize=10, loc="left")
    ax.set_xlabel("along-track distance (m)")
    ax.set_ylabel("relief (m)" if relief_col else "height (m)")
    return ax


def plot_bias_by_class(tables, title, ax=None, metric="bias"):
    """Grouped bars of a metric per height class for several schemes. tables: {scheme: metrics table}."""
    ax = ax or plt.gca()
    names = list(tables)
    classes = [i for i in tables[names[0]].index if i not in ("all", "spurious_veg_rate")]
    w = 0.8 / len(names)
    for j, nm in enumerate(names):
        v = tables[nm].reindex(classes)[metric]
        ax.bar(np.arange(len(classes)) + j * w - 0.4 + w / 2, v, w, label=nm, color=SCHEME_COLORS.get(nm))
    ax.axhline(0, c="k", lw=0.6)
    ax.set_xticks(np.arange(len(classes)), classes, rotation=30)
    ax.set_ylabel(f"{metric} (m)")
    ax.set_title(title, loc="left", fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(axis="x", visible=False)
    return ax


def plot_scatter(ax, est, ref, title, lim=None, cmap="Greys"):
    """Density of ICESat-2 vs reference heights (log counts), 1:1 line, n / bias / RMSE / r². Square panel."""
    est, ref = np.asarray(est, float), np.asarray(ref, float)
    ok = np.isfinite(est) & np.isfinite(ref)
    lim = lim or max(5, np.nanpercentile(np.r_[est[ok], ref[ok]], 99.5))
    hb = ax.hexbin(ref[ok], est[ok], gridsize=40, extent=(0, lim, 0, lim), mincnt=1, bins="log", cmap=cmap, lw=0)
    ax.plot([0, lim], [0, lim], c="#d7301f", lw=0.8)
    e = est[ok] - ref[ok]
    r2 = r_squared(est[ok], ref[ok])
    ax.text(0.03, 0.97, f"n = {ok.sum():,}\nbias = {e.mean():+.2f} m\nRMSE = {np.sqrt(np.mean(e**2)):.2f} m\nr² = {r2:.2f}",
            transform=ax.transAxes, va="top", fontsize=8, bbox=dict(fc="white", ec="none", alpha=0.8))
    ax.set_xlim(0, lim); ax.set_ylim(0, lim); ax.set_aspect("equal")
    ax.set_xlabel("reference height (m)")
    ax.set_ylabel("ICESat-2 h_canopy (m)")
    ax.set_title(title, fontsize=10, loc="left")
    return hb


def segments_all_versions(ph, cfgs, cfg, phoreal=None):
    """30 m segments from the same photons for every version: ATL08 v007 classes in our binning (h_canopy_atl08),
    our reclassifier for each config in `cfgs` ({'v0.2': cfg02, ...} -> h_canopy_v02, low_signal_v02, ...), and
    optionally the current v7 30 m PhoREAL segments matched to the nearest segment on the same track (h_canopy_phoreal).
    All versions use the same 30 m along-track grid, so they line up by (track_id, seg)."""
    import geopandas as gpd
    import icesat2_photon_lib as ipl
    keys = ["track_id", "seg"]
    geo = ["lon", "lat", "lon0", "lat0", "lon1", "lat1", "solar_elevation", "strong", "year", "doy", "geometry"]
    nat = ipl.segment_metrics(ipl.native_relief(ph, cfg), cfg, "atl08_class", "relief_atl08", "atl08")
    frames = {"atl08": nat}
    for v, c in cfgs.items():
        frames[v.replace(".", "")] = ipl.segment_metrics(ipl.reclassify(ph, c), c, "class_new", "relief_new", "new")
    if not any(len(f) for f in frames.values()):
        return gpd.GeoDataFrame()
    base = pd.concat([f[keys + geo] for f in frames.values() if len(f)], ignore_index=True).drop_duplicates(keys)
    for t, f in frames.items():
        if not len(f):
            continue
        cols = {"h_canopy": f"h_canopy_{t}"}
        if t != "atl08":
            cols.update({"low_signal": f"low_signal_{t}", "short_veg_flag": f"short_veg_{t}",
                         "n_canopy": f"n_canopy_{t}", "canopy_signal_photons": f"canopy_signal_{t}"})
            # v0.4 presence test columns, where the config has them
            cols.update({c: f"{c}_{t}" for c in ("veg_present", "veg_detectable", "veg_unmeasured", "presence_sigma",
                                                 "ground_slope_deg") if c in f})
        base = base.merge(f[keys + list(cols)].rename(columns=cols), on=keys, how="left")
    base = gpd.GeoDataFrame(base, geometry="geometry", crs=4326)
    if phoreal is not None and len(phoreal):
        base = ipl.match_segments(base, phoreal.to_crs(4326)[["track_id", "geometry", "h_canopy"]], ["h_canopy"],
                                  suffix="_phoreal")
    return base
