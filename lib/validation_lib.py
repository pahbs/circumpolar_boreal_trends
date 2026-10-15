"""Validation metrics and standard plots for the ATL03 reclassification work."""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

CLASS_COLORS = {"noise": "#bdbdbd", "ground": "#a6611a", "canopy": "#1b9e77", "top": "#00441b",
                "buffer": "#fdb863", "none": "#ffffff", "unclassified": "#d7301f"}
ATL08_NAMES = {0: "noise", 1: "ground", 2: "canopy", 3: "top", 4: "unclassified"}
NEW_NAMES = {0: "noise", 1: "ground", 2: "canopy", 3: "top"}
# The three versions of 30 m segments compared throughout (all from the same ATL03 v007 photons):
LABEL_CURRENT = "current v7 30 m (ATL08 classes → PhoREAL)"    # what our training files contain today
LABEL_CHECK = "ATL08 classes → our 30 m (check)"                # isolates our binning from our classification
LABEL_NEW = "reclassified photons → our 30 m (new)"           # the new product
SCHEME_COLORS = {LABEL_CURRENT: "#7570b3", LABEL_CHECK: "#d95f02", LABEL_NEW: "#1b9e77"}
# Photon classifications compared throughout:
PHOTON_ATL08 = "ATL08 v007 photon classes"
PHOTON_NEW = "reclassified photon classes (v0.1)"
PHOTON_REF = "reference photon labels"


def height_class_labels(edges):
    return [f"{a}-{b} m" if b < 60 else f"{a}+ m" for a, b in zip(edges[:-1], edges[1:])]


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
    return ax


def plot_scatter(ax, est, ref, title, lim=None):
    est, ref = np.asarray(est, float), np.asarray(ref, float)
    ok = np.isfinite(est) & np.isfinite(ref)
    lim = lim or max(5, np.nanpercentile(np.r_[est[ok], ref[ok]], 99.5))
    ax.hexbin(ref[ok], est[ok], gridsize=40, extent=(0, lim, 0, lim), mincnt=1, bins="log", cmap="viridis")
    ax.plot([0, lim], [0, lim], c="k", lw=0.7)
    e = est[ok] - ref[ok]
    ax.text(0.03, 0.97, f"n={ok.sum()}\nbias={e.mean():.2f} m\nRMSE={np.sqrt(np.mean(e**2)):.2f} m",
            transform=ax.transAxes, va="top", fontsize=8)
    ax.set_xlabel("reference (m)")
    ax.set_ylabel("ICESat-2 (m)")
    ax.set_title(title, fontsize=10, loc="left")
    return ax
