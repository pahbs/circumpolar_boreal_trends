"""All validation results in one table, and the figures of the outward-facing summary (notebook 11).

One row per 30 m segment that has a reference height, from every reference (LVIS 2019, CanElevation, G-LiHT, Seward UAV,
Seward field),
with one column per version: today (ATL08 · PhoREAL), control (ATL08 · our binning), v0.2 ... LATEST. Each run folder
runs/v0.N holds today, control, the previous version and v0.N; older versions come from older run folders. Versions not
run against a reference are NaN there (v0.3 was validated only on LVIS and CanElevation).

Colours (validated with the dataviz checks, 17 Oct 2026): today = neutral gray; our versions = one blue ramp, light to dark
in development order, so the darkest bar is the current best; control (appendix only) = light gray with direct labels.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

import validation_lib as val

TODAY, CONTROL = "today", "control"
LATEST = "v0.6"
VERSIONS = [TODAY, "v0.2", "v0.3", "v0.4", "v0.5", "v0.6"]  # shown in the main figures
COLORS = {TODAY: "#898781", "v0.2": "#bcd7f7", "v0.3": "#86b6ef", "v0.4": "#4f93e3", "v0.5": "#2a6bc2", "v0.6": "#123c74",
          CONTROL: "#c3c2b7"}
LABELS = {TODAY: "Today: ATL08 · PhoREAL", CONTROL: "Control: ATL08 · our binning", "v0.2": "Reclassified v0.2",
          "v0.3": "Reclassified v0.3", "v0.4": "Reclassified v0.4", "v0.5": "Reclassified v0.5",
          "v0.6": "Reclassified v0.6 (final)"}
REFS = ["LVIS 2019", "CanElevation lidar", "G-LiHT lidar", "Seward UAV", "Seward field (2 m)"]
INDEPENDENT = {"LVIS 2019": True, "CanElevation lidar": True, "G-LiHT lidar": False, "Seward UAV": False, "Seward field (2 m)": False}
REF_NOTE = {"LVIS 2019": "airborne waveform lidar · Alaska + W Canada · independent",
            "CanElevation lidar": "airborne lidar · 13 provinces / territories · independent",
            "G-LiHT lidar": "airborne lidar · interior Alaska, Kenai · development site",
            "Seward UAV": "drone surface model · Seward Peninsula tundra · development site",
            "Seward field (2 m)": "field heights, tallest within 2 m of each point · Seward Peninsula · development site"}
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
CLASSES = [0, 1, 2, 5, 10, 15, 20, 60]
CLASS_LABELS = val.height_class_labels(CLASSES)


def _read(pattern_dir, pattern):
    files = sorted(Path(pattern_dir).glob(pattern))
    return pd.concat([pd.DataFrame(gpd.read_parquet(f).drop(columns="geometry", errors="ignore")) for f in files],
                     ignore_index=True) if files else pd.DataFrame()


def _vcol(v):
    return "h_canopy_" + v.replace(".", "")


def load_all(work):
    """Every reference's segments in one wide table (see module docstring)."""
    work = Path(work); runs = work / "runs"; parts = []
    nv = lambda v: f"v0.{int(v[3:]) - 1}"                    # previous version
    for ref, sub, fn, k, region, ref_h, keep in [
            ("LVIS 2019", "validation_lvis", "segments_lvis.parquet", ["lvis_stem", "track_id", "seg"], "region", "lvis_RH098_mean", lambda a: a.lvis_n >= 6),
            ("CanElevation lidar", "validation_canelevation", "segments_canelevation.parquet", ["box_id", "track_id", "seg"], "prefix", "als_rh98", lambda a: a.als_n > 0)]:
        # notebooks 09 / 10: run LATEST has today, control, previous and LATEST; each older run adds its previous version
        a = pd.DataFrame(gpd.read_parquet(runs / LATEST / sub / fn).drop(columns="geometry"))
        v = LATEST
        while v != "v0.2":
            f = runs / nv(v) / sub / fn
            if not f.exists():
                break
            b = pd.DataFrame(gpd.read_parquet(f).drop(columns="geometry"))
            col = _vcol(nv(nv(v)))
            if col in b and col not in a:
                a = a.merge(b[k + [col]].drop_duplicates(k), on=k, how="left")
            v = nv(v)
        a = a[keep(a)]
        parts.append(pd.DataFrame({"reference": ref, "region": a[region], "ref_h": a[ref_h], TODAY: a.h_canopy_phoreal,
                                   CONTROL: a.h_canopy_atl08, **{x: a.get(_vcol(x), np.nan) for x in VERSIONS[1:]},
                                   "solar_elevation": a.solar_elevation, "strong": a.strong,
                                   "slope_deg": a.get("ground_slope_deg_" + LATEST.replace(".", ""))}))
    # G-LiHT (notebook 05) and Seward (notebook 01): one version per run folder (v0.3 not run here)
    k = ["track_id", "seg"]
    for ref, sub, pat in [("G-LiHT lidar", "validation", "tile_*_segments_als.parquet"), ("Seward UAV", "seward", "*_segments.parquet")]:
        a = _read(runs / LATEST / sub, pat)
        if not len(a):
            continue
        a = a.rename(columns={"h_canopy": _vcol(LATEST)})
        for x in [v for v in VERSIONS[1:] if v != LATEST]:
            b = _read(runs / x / sub, pat)
            if len(b) and "h_canopy" in b:
                a = a.merge(b[k + ["h_canopy"]].rename(columns={"h_canopy": _vcol(x)}).drop_duplicates(k), on=k, how="left")
        a = a[(a.als_n > 0) | (a.get("field_n", 0) > 0)]
        if "disturbed_frac" in a:
            a = a[a.disturbed_frac.fillna(0) <= 0.10]
        refs = [(ref, a.als_rh98)]
        if ref == "Seward UAV" and "field_max_200" in a:
            # Seward field: tallest field height within 2 m of each field point inside the segment (max over the points)
            refs.append(("Seward field (2 m)", a.field_max_200.where(a.get("field_n", 0) > 0)))
        for r, ref_h in refs:
            parts.append(pd.DataFrame({"reference": r, "region": a.get("region", pd.Series("Seward", index=a.index)).fillna("Seward"),
                                       "ref_h": ref_h, TODAY: a.h_canopy_phoreal, CONTROL: a.h_canopy_atl08,
                                       **{x: a.get(_vcol(x), np.nan) for x in VERSIONS[1:]}, "solar_elevation": a.solar_elevation,
                                       "strong": a.strong, "slope_deg": a.get("ground_slope_deg")}))
    d = pd.concat(parts, ignore_index=True)
    d = d[np.isfinite(d.ref_h)].copy()
    d["light"] = np.where(d.solar_elevation > 0, "day", "night")
    d["beam"] = np.where(d.strong.astype(bool), "strong", "weak")
    d["height_class"] = pd.cut(d.ref_h, CLASSES, right=False, labels=CLASS_LABELS)
    d["independent"] = d.reference.map(INDEPENDENT)
    return d


def versions_for(d, ref, versions=VERSIONS):
    """Versions with results for this reference."""
    g = d[d.reference == ref]
    return [v for v in versions if g[v].notna().any()]


def common(d, ref, versions=VERSIONS):
    """Segments of one reference for which every version run there reports a height."""
    g = d[d.reference == ref]
    return g.dropna(subset=versions_for(d, ref, versions))


def summary(d, versions=VERSIONS):
    """Per reference x version: n, coverage, bias, RMSE, r², spurious vegetation, forest wrongly at 0 m (common segments)."""
    rows = []
    for ref in REFS:
        g_all = d[d.reference == ref]
        if not len(g_all):
            continue
        g = common(d, ref, versions)
        for v in versions_for(d, ref, versions):
            e = g[v] - g.ref_h
            bare, forest = g.ref_h < 1, g.ref_h >= 5
            rows.append({"reference": ref, "version": v, "n_common": len(g), "coverage": g_all[v].notna().mean(),
                         "bias": e.mean(), "rmse": np.sqrt((e ** 2).mean()), "r2": val.r_squared(g[v], g.ref_h),
                         # shares need >= 10 segments in the class (Seward field has 2 forest segments)
                         "spurious_veg": (bare & (g[v] > 2)).sum() / bare.sum() if bare.sum() >= 10 else np.nan,
                         "forest_at_0m": (forest & (g[v] == 0)).sum() / forest.sum() if forest.sum() >= 10 else np.nan,
                         "bias_tall_10m+": e[g.ref_h >= 10].mean(), "bias_short_0-2m": e[g.ref_h < 2].mean()})
    return pd.DataFrame(rows)


def by_class(d, versions=VERSIONS):
    """Bias and zero share per reference x version x reference height class (common segments)."""
    rows = []
    for ref in REFS:
        if not (d.reference == ref).any():
            continue
        g = common(d, ref, versions)
        for v in versions_for(d, ref, versions):
            for cl, gg in g.groupby("height_class", observed=True):
                e = gg[v] - gg.ref_h
                rows.append({"reference": ref, "version": v, "height_class": cl, "n": len(gg), "bias": e.mean(),
                             "zero_share": (gg[v] == 0).mean()})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ figures

def style_axes(ax, ylabel=None, zero_line=True):
    ax.grid(axis="x", visible=False); ax.grid(axis="y", color=GRID, lw=0.6)
    for s in ("left",):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(axis="both", colors=INK2, length=0)
    if zero_line:
        ax.axhline(0, color=INK2, lw=0.8, zorder=3)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2)


def grouped_bars(ax, table, categories, versions, value, width=0.84, gap=0.04, fmt=None, label_versions=()):
    """Bars per category, one per version (fixed order and colour); a small gap separates neighbours."""
    if not versions or not len(table):
        ax.text(0.5, 0.5, "not run yet", transform=ax.transAxes, ha="center", color=MUTED); return
    nv = len(versions); w = width / nv
    for j, v in enumerate(versions):
        t = table[table.version == v].set_index("cat").reindex(categories)
        x = np.arange(len(categories)) - width / 2 + (j + 0.5) * w
        ax.bar(x, t[value].to_numpy(), w - gap, color=COLORS[v], label=LABELS[v], zorder=2)
        if v in label_versions and fmt:
            for xi, yi in zip(x, t[value].to_numpy()):
                if np.isfinite(yi):
                    ax.text(xi, yi, fmt(yi), ha="center", va="bottom" if yi >= 0 else "top", fontsize=7.5, color=INK2)
    ax.set_xticks(np.arange(len(categories)), categories)


def lede(fig, title, subtitle=None):
    """Figure headline in primary ink and a one-line subtitle in secondary ink, left-aligned."""
    fig.text(0.01, 1.0, title, ha="left", va="bottom", fontsize=13, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.01, 0.985, subtitle, ha="left", va="top", fontsize=9.5, color=INK2)


def legend_row(fig, versions, y=-0.02):
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[v]) for v in versions]
    fig.legend(handles, [LABELS[v] for v in versions], loc="upper center", bbox_to_anchor=(0.5, y), ncol=len(versions),
               frameon=False, fontsize=9, handlelength=1.2, columnspacing=1.6)


def hexscatter(ax, est, ref, title, lim=30, color="#184f95", light="#cde2fb"):
    """Density of ICESat-2 vs reference heights, 1:1 line, n / bias / RMSE / r² as text in ink colours."""
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("ramp", [light, color])
    ok = np.isfinite(est) & np.isfinite(ref)
    if ok.sum() < 3:
        ax.text(0.5, 0.5, "not run yet", transform=ax.transAxes, ha="center", color=MUTED); ax.set_title(title, fontsize=10, color=INK, loc="left"); return
    ax.hexbin(ref[ok], est[ok], gridsize=36, extent=(0, lim, 0, lim), mincnt=1, bins="log", cmap=cmap, lw=0, zorder=2)
    ax.plot([0, lim], [0, lim], color=INK2, lw=0.8, zorder=3)
    e = est[ok] - ref[ok]
    ax.text(0.04, 0.96, f"r² {val.r_squared(est[ok], ref[ok]):.2f}\nbias {e.mean():+.1f} m\nRMSE {np.sqrt(np.mean(e ** 2)):.1f} m\nn {ok.sum():,}",
            transform=ax.transAxes, va="top", fontsize=8.5, color=INK,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.85), zorder=4)
    ax.set_xlim(0, lim); ax.set_ylim(0, lim); ax.set_aspect("equal")
    ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="normal")
    ax.grid(color=GRID, lw=0.5); ax.tick_params(colors=INK2, length=0)
    for s in ax.spines.values():
        s.set_visible(False)


# ------------------------------------------------------------------ validation map

MAP_COLORS = {"LVIS 2019": "#d95f02", "CanElevation lidar": "#7570b3", "G-LiHT lidar": "#1b9e77", "Seward UAV": "#e7298a",
              "Seward field (2 m)": "#0b0b0b",
              "dev": "crimson", "test": "#0b0b0b"}


def _latest(runs, rel):
    """Newest run folder (v0.N, highest N) that has `rel`; None if none has it."""
    for r in sorted(Path(runs).glob("v0.*"), key=lambda p: [int(x) for x in p.name[1:].split(".")], reverse=True):
        if (r / rel).exists():
            return r / rel
    return None


def validation_sites(work, boreal_tiles, dev_tiles=(3457, 3553, 3836, 3928), test_tiles=(3638,), seward_dir=None):
    """Every reference used for validation, in EPSG:4326: LVIS 2019 segments (notebook 09), CanElevation boxes (10),
    G-LiHT strips at the development tiles (05), Seward UAV transects and field points (01; with seward_dir), development tiles and production test
    tiles (08). Site selections use fixed seeds, so they are the same in every run; the newest run that has them is read."""
    work = Path(work); runs = work / "runs"
    out = {}
    f = _latest(runs, "validation_lvis/selected_segments.parquet")
    out["LVIS 2019"] = gpd.read_parquet(f).to_crs(4326) if f else None
    lv = work / "lvis" / "LVIS_ABoVE_spatial_footprints_2017_2019.gpkg"
    out["lvis_all"] = gpd.read_file(lv, layer="LVISF3_2019").to_crs(4326) if lv.exists() else None
    f = _latest(runs, "validation_canelevation/boxes.parquet")
    out["CanElevation lidar"] = gpd.read_parquet(f).to_crs(4326) if f else None
    strips = gpd.read_parquet(work / "inventory" / "glihit_strips_alaska.parquet")
    used = set()
    for t in dev_tiles:
        fn = work / "glihit" / f"tile_{t}" / "strips.csv"
        if fn.exists():
            used |= set(pd.read_csv(fn).granule)
    out["G-LiHT lidar"] = strips[strips.granule.isin(used)].to_crs(4326)
    out["Seward UAV"] = gpd.read_parquet(work / "inventory" / "seward_sites.parquet").to_crs(4326)
    if seward_dir is not None and (Path(seward_dir) / "sew_pen_field_data_2024.gpkg").exists():
        out["Seward field (2 m)"] = gpd.read_file(Path(seward_dir) / "sew_pen_field_data_2024.gpkg").to_crs(4326)
    tiles = gpd.read_file(boreal_tiles)
    tiles["tile_num"] = tiles.tile_num.astype(int)
    out["boreal"] = tiles.to_crs(4326)
    out["dev"] = out["boreal"][out["boreal"].tile_num.isin(dev_tiles)]
    out["test"] = out["boreal"][out["boreal"].tile_num.isin(test_tiles)]
    return out


def validation_map(sites, add_basemap=None, map_axes=None):
    """One map of every validation reference (same style as the LVIS and CanElevation maps of notebooks 09-10: ESRI Light
    Gray basemap, clean frame), left: all of North America in Canada Lambert (EPSG:3979); right: the Alaska development
    sites in Alaska Albers (EPSG:3338). Independent references are filled markers, development sites are outlined areas."""
    import matplotlib.patches as mpatches
    from matplotlib.lines import Line2D
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(17, 7.6), gridspec_kw={"width_ratios": [1.65, 1]})
    for ax, crs in [(a1, 3979), (a2, 3338)]:
        b = sites["boreal"].to_crs(crs)
        b.plot(ax=ax, color="#d6cfb4", lw=0, alpha=0.6, zorder=1)                    # boreal / tundra tile domain
        if sites.get("lvis_all") is not None:
            sites["lvis_all"].to_crs(crs).plot(ax=ax, color="0.62", lw=0, alpha=0.5, zorder=2)
        g = sites.get("LVIS 2019")
        if g is not None:
            c = g.to_crs(crs).geometry.representative_point()
            ax.scatter(c.x, c.y, s=46, marker="o", color=MAP_COLORS["LVIS 2019"], edgecolor="k", lw=0.5, zorder=6)
        g = sites.get("CanElevation lidar")
        if g is not None:
            c = g.to_crs(crs).geometry.centroid
            ax.scatter(c.x, c.y, s=46, marker="s", color=MAP_COLORS["CanElevation lidar"], edgecolor="k", lw=0.5, zorder=6)
        sites["G-LiHT lidar"].to_crs(crs).plot(ax=ax, color=MAP_COLORS["G-LiHT lidar"], lw=0.6, edgecolor=MAP_COLORS["G-LiHT lidar"], zorder=4)
        sg = sites["Seward UAV"].to_crs(crs)
        sg.plot(ax=ax, color=MAP_COLORS["Seward UAV"], edgecolor=MAP_COLORS["Seward UAV"], lw=1.5, zorder=5)
        c = sg.geometry.centroid
        ax.scatter(c.x, c.y, s=30, marker="^", color=MAP_COLORS["Seward UAV"], edgecolor="k", lw=0.4, zorder=6)
        if sites.get("Seward field (2 m)") is not None and crs == 3338:      # points only show at the Alaska scale
            sites["Seward field (2 m)"].to_crs(crs).plot(ax=ax, color=MAP_COLORS["Seward field (2 m)"], markersize=3, zorder=8)
        sites["dev"].to_crs(crs).boundary.plot(ax=ax, color=MAP_COLORS["dev"], lw=1.6, zorder=7)
        sites["test"].to_crs(crs).boundary.plot(ax=ax, color=MAP_COLORS["test"], lw=1.4, ls="--", zorder=7)
    # extents: all references (left); development tiles + Seward + Alaska LVIS (right)
    allpts = pd.concat([gpd.GeoSeries(sites[k].to_crs(3979).geometry) for k in ("LVIS 2019", "CanElevation lidar", "G-LiHT lidar", "Seward UAV")
                        if sites.get(k) is not None])
    x0, y0, x1, y1 = allpts.total_bounds; p = 0.06 * max(x1 - x0, y1 - y0)
    a1.set_xlim(x0 - p, x1 + p); a1.set_ylim(y0 - p, y1 + p)
    ak = pd.concat([gpd.GeoSeries(sites["dev"].to_crs(3338).geometry), gpd.GeoSeries(sites["Seward UAV"].to_crs(3338).geometry),
                    gpd.GeoSeries(sites["test"].to_crs(3338).geometry)])
    x0, y0, x1, y1 = ak.total_bounds; p = 0.08 * max(x1 - x0, y1 - y0)
    a2.set_xlim(x0 - p, x1 + p); a2.set_ylim(y0 - p, y1 + p)
    for ax, crs, t in [(a1, 3979, "All validation references"), (a2, 3338, "Alaska development sites")]:
        if add_basemap:
            add_basemap(ax, crs)
        if map_axes:
            map_axes(ax)
        ax.set_title(t, loc="left", fontsize=11, color=INK)
    n = lambda k: len(sites[k]) if sites.get(k) is not None else 0
    handles = [Line2D([], [], marker="o", ls="", ms=8, mfc=MAP_COLORS["LVIS 2019"], mec="k", label=f"LVIS 2019 flight segments ({n('LVIS 2019')}) · independent"),
               mpatches.Patch(color="0.62", alpha=0.5, label="all LVIS 2019 flights"),
               Line2D([], [], marker="s", ls="", ms=8, mfc=MAP_COLORS["CanElevation lidar"], mec="k", label=f"CanElevation lidar boxes, 4 × 4 km ({n('CanElevation lidar')}) · independent"),
               mpatches.Patch(color=MAP_COLORS["G-LiHT lidar"], label=f"G-LiHT lidar strips ({n('G-LiHT lidar')}) · development"),
               Line2D([], [], marker="^", ls="", ms=8, mfc=MAP_COLORS["Seward UAV"], mec="k", label=f"Seward UAV transects ({n('Seward UAV')}) · development"),
               *([Line2D([], [], marker="o", ls="", ms=3, mfc=MAP_COLORS["Seward field (2 m)"], mec="none",
                         label=f"Seward field points ({n('Seward field (2 m)')}) · development")] if sites.get("Seward field (2 m)") is not None else []),
               Line2D([], [], color=MAP_COLORS["dev"], lw=1.8, label="development tiles " + ", ".join(str(t) for t in sites["dev"].tile_num)),
               Line2D([], [], color=MAP_COLORS["test"], lw=1.4, ls="--", label="production test tile " + ", ".join(str(t) for t in sites["test"].tile_num)),
               mpatches.Patch(color="#d6cfb4", alpha=0.6, label="boreal / tundra tile domain")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=3, frameon=False, fontsize=9)
    return fig
