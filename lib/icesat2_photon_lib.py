"""ICESat-2 ATL03 v007 photon reclassification, 30 m segments and canopy cover.

Every threshold comes from the versioned config (config/atl03_reclass_v*.yaml).
Notebooks call these functions; no algorithm code lives in notebooks.

Photon classes used throughout:
    0 noise, 1 ground, 2 canopy, 3 top of canopy (ATL08 only), 4 unclassified (ATL08 only)
    new classifier: 0 noise, 1 ground, 2 canopy, 3 canopy-top photon recovered from the noise filter
Reference labels (from airborne/UAV DTM + CHM): 'ground', 'canopy', 'buffer', 'noise', 'none'

Steps (see docs/atl03_reclassification_plan.md, section 4):
    granules_from_cmr -> fetch_photons -> reclassify -> segment_metrics -> fit_reflectance_ratio -> canopy_cover
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import yaml
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

C_LIGHT = 299_792_458.0
TRACK_COLS = ["rgt", "cycle", "gt"]
REPO_DIR = Path(__file__).resolve().parents[1]


# ============================================================ config and provenance

def load_config(path=None, profile=None):
    """Read the config and resolve the path profile ('adapt' or 'maap'; auto-detected if None)."""
    path = Path(path or REPO_DIR / "config" / "atl03_reclass_v0.1.yaml")
    cfg = yaml.safe_load(path.read_text())
    if profile is None:
        profile = "maap" if os.path.isdir("/projects") and os.environ.get("MAAP_API_HOST") else "adapt"
    cfg["profile"] = profile
    cfg["paths"] = cfg["profiles"][profile]
    cfg["config_path"] = str(path)
    cfg["config_sha1"] = hashlib.sha1(path.read_bytes()).hexdigest()[:12]
    return cfg


def provenance(cfg, **extra):
    """Metadata recorded with every output: code commit, config version/hash, SlideRule version, date."""
    try:
        commit = subprocess.run(["git", "-C", str(REPO_DIR), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(REPO_DIR), "status", "--porcelain", "lib", "config"],
                                    capture_output=True, text=True).stdout.strip())
    except Exception:
        commit, dirty = "unknown", None
    try:
        import sliderule
        sr_client = sliderule.__version__
    except Exception:
        sr_client = None
    meta = {"repo": "circumpolar_boreal_trends", "git_commit": commit, "git_dirty_lib_or_config": dirty,
            "config_version": cfg["version"], "config_sha1": cfg["config_sha1"],
            "sliderule_client": sr_client, "processed_utc": dt.datetime.utcnow().isoformat(timespec="seconds")}
    meta.update(extra)
    return meta


def write_parquet(df, path, meta):
    """Write a (Geo)DataFrame to parquet with provenance in the file metadata (key 'atl03_reclass')."""
    import pyarrow.parquet as pq
    path = str(path)
    if not path.startswith("s3://"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    if isinstance(df, gpd.GeoDataFrame):
        df.to_parquet(path)
    else:
        df.to_parquet(path, index=False)
    if not path.startswith("s3://"):
        table = pq.read_table(path)
        md = dict(table.schema.metadata or {})
        md[b"atl03_reclass"] = json.dumps(meta, default=str).encode()
        pq.write_table(table.replace_schema_metadata(md), path)
    return path


def read_provenance(path):
    import pyarrow.parquet as pq
    md = pq.read_schema(path).metadata or {}
    return json.loads(md.get(b"atl03_reclass", b"{}"))


# ============================================================ granules (CMR) and SlideRule

def granules_from_cmr(geom, years, months, short_name="ATL03", release="007"):
    """ATL03/ATL08 granule names intersecting geom (lon/lat shapely geometry) in the given years and months.
    Looked up in CMR directly so the exact release and inputs are explicit and recorded."""
    w, s, e, n = geom.bounds
    names = []
    for y in years:
        url = "https://cmr.earthdata.nasa.gov/search/granules.json"
        params = {"short_name": short_name, "version": release, "bounding_box": f"{w},{s},{e},{n}",
                  "temporal": f"{y}-{min(months):02d}-01T00:00:00Z,{y}-{max(months):02d}-30T23:59:59Z",
                  "page_size": 2000}
        r = requests.get(url, params=params, timeout=120)
        r.raise_for_status()
        for g in r.json()["feed"]["entry"]:
            name = g.get("producer_granule_id") or g["title"].split(":")[-1]
            if int(g["time_start"][5:7]) in months:
                names.append(name)
    return sorted(set(names))


def sliderule_init(organization=None, verbose=False):
    import sliderule
    if organization:
        sliderule.init("slideruleearth.io", organization=organization, verbose=verbose, desired_nodes=5,
                       time_to_live=720)
    else:
        sliderule.init(verbose=verbose)
    return sliderule


def to_sliderule_poly(geom):
    """Shapely polygon (lon/lat) -> SlideRule poly (counter-clockwise list of lat/lon dicts)."""
    from shapely.geometry import polygon as shp_polygon
    g = shp_polygon.orient(geom.convex_hull if geom.geom_type != "Polygon" else geom, sign=1.0)
    return [{"lon": float(x), "lat": float(y)} for x, y in g.exterior.coords]


def fetch_photons(geom, granules, cfg, with_atl08_fields=True):
    """All ATL03 photons (signal and background) in geom from the named granules, with ATL08 v007 classes,
    the ATL03 v007 photon weight (YAPC score) and shot identifiers. Returns a GeoDataFrame (EPSG:7912)."""
    import sliderule
    ic = cfg["icesat2"]
    parms = {
        "poly": to_sliderule_poly(geom),
        "srt": 0,
        "cnf": ic["atl03_cnf"],
        "quality_ph": ic["quality_ph"],
        "atl08_class": ["atl08_noise", "atl08_ground", "atl08_canopy", "atl08_top_of_canopy",
                        "atl08_unclassified"],
        "yapc": {"version": 0, "score": 0},
        "atl03_ph_fields": ["ph_id_pulse", "pce_mframe_cnt"],
    }
    if with_atl08_fields:
        parms["atl08_fields"] = ["segment_snowcover", "segment_landcover", "msw_flag"]
    return _run_by_granule("atl03x", parms, granules, cfg, add_fields=True)


def _run_by_granule(api, parms, granules, cfg, add_fields=False):
    """One SlideRule request for all granules; on failure, one request per granule (failures logged)."""
    import sliderule
    if not granules:
        return gpd.GeoDataFrame()
    try:
        frames = [sliderule.run(api, parms, resources=list(granules))]
    except Exception as err:
        print(f"  batch request failed ({err}); retrying per granule")
        frames = []
        for g in granules:
            try:
                frames.append(sliderule.run(api, parms, resources=[g]))
            except Exception as err2:      # one bad granule must not stop the request
                print(f"  {g}: {err2}")
    frames = [f for f in frames if f is not None and len(f)]
    if not frames:
        return gpd.GeoDataFrame()
    out = gpd.GeoDataFrame(pd.concat(frames), crs=frames[0].crs).reset_index()
    lut = {granule_parts(g): g for g in granules}
    out["granule"] = [lut.get((r, c, rg)) for r, c, rg in zip(out["rgt"], out["cycle"], out["region"])]
    if add_fields:
        out = add_photon_fields(out, cfg)
    else:
        out["track_id"] = out["rgt"].astype(str) + "_" + out["cycle"].astype(str) + "_" + out["gt"].astype(str)
    return out


def add_photon_fields(gdf, cfg):
    """Derived per-photon fields: time, year, doy, strong beam flag, shot id, lon/lat."""
    tcol = "time_ns" if "time_ns" in gdf else "time"
    t = pd.to_datetime(gdf[tcol])
    gdf["year"], gdf["month"], gdf["doy"] = t.dt.year, t.dt.month, t.dt.dayofyear
    gdf["strong"] = gdf["spot"].isin(cfg["icesat2"]["strong_spots"])
    gdf["lon"], gdf["lat"] = gdf.geometry.x, gdf.geometry.y
    if "pce_mframe_cnt" in gdf and "ph_id_pulse" in gdf:
        gdf["shot"] = gdf["pce_mframe_cnt"].astype("int64") * 1000 + gdf["ph_id_pulse"].astype("int64")
    gdf["track_id"] = gdf["rgt"].astype(str) + "_" + gdf["cycle"].astype(str) + "_" + gdf["gt"].astype(str)
    return gdf


def fetch_phoreal(geom, granules, cfg):
    """30 m segments from SlideRule PhoREAL with ATL08 v007 classes: the same processing as our current
    v7 training files (process_atl08_boreal.py), for a like-for-like comparison."""
    import sliderule
    seg = cfg["segments"]
    parms = {
        "poly": to_sliderule_poly(geom), "srt": 0, "len": seg["length_m"], "res": seg["length_m"],
        "pass_invalid": True,
        "atl08_class": ["atl08_ground", "atl08_canopy", "atl08_top_of_canopy"],
        "atl08_fields": ["canopy/h_canopy_uncertainty", "h_dif_ref", "msw_flag", "sigma_topo",
                         "segment_landcover", "canopy/segment_cover", "segment_snowcover",
                         "terrain/h_te_uncertainty"],
        "phoreal": dict(seg["phoreal"]),
    }
    return _run_by_granule("atl03x", parms, granules, cfg)


# ============================================================ reference photon labels

def reference_label(h, ref_ground, ref_canopy_top, cfg):
    """Label photons from reference ground and canopy-top heights summarised over the footprint
    (after Purslow et al. 2023, Fig. 1): ground and canopy windows, buffers, noise beyond the buffers.
    h, ref_ground, ref_canopy_top: arrays of absolute heights in the same vertical datum."""
    rl = cfg["reference_labels"]
    h, g, top = map(np.asarray, (h, ref_ground, ref_canopy_top))
    dz = h - g
    canopy_top = np.maximum(top - g, 0) + rl["canopy_top_buffer_m"]
    lab = np.full(h.shape, "buffer", dtype=object)
    lab[np.abs(dz) <= rl["ground_halfwidth_m"]] = "ground"
    can = (dz > rl["ground_halfwidth_m"]) & (dz <= canopy_top)
    lab[can] = "canopy"
    lab[(dz > canopy_top + rl["noise_buffer_m"]) | (dz < -rl["ground_halfwidth_m"] - rl["noise_buffer_m"])] = "noise"
    lab[~np.isfinite(dz) | ~np.isfinite(top)] = "none"
    return lab


# ============================================================ reclassifier

def expected_noise_count(background_rate, cfg):
    """Expected background photons in the noise-filter window around a photon (Poisson mean).
    background_rate [photons/s] x window time (2 x height / c) x shots in the along-track window."""
    nz = cfg["reclass"]["noise"]
    window_s = 2 * (2 * nz["window_vert_m"]) / C_LIGHT
    shots = 2 * nz["window_along_m"] / cfg["icesat2"]["shot_spacing_m"]
    return np.asarray(background_rate, float) * window_s * shots


def noise_filter(x, h, background_rate, cfg):
    """Step 1. Signal where the local photon count clearly exceeds the expected background count.
    Box window: +/- window_along_m along track, +/- window_vert_m vertically."""
    nz = cfg["reclass"]["noise"]
    scale = nz["window_along_m"] / nz["window_vert_m"]
    pts = np.column_stack([x, h * scale])
    tree = cKDTree(pts)
    count = tree.query_ball_point(pts, r=nz["window_along_m"], p=np.inf, return_length=True) - 1
    lam = expected_noise_count(background_rate, cfg)
    thresh = np.maximum(lam + nz["k_sigma"] * np.sqrt(lam), nz["min_count"])
    return count >= thresh, count, lam


def _rolling_median(v, n):
    return pd.Series(v).rolling(n, center=True, min_periods=1).median().to_numpy()


def ground_halfwidth(slope, cfg):
    """Vertical half-width of the ground returns at a given along-track ground slope (m/m).

    v0.4 (`ground.slope_window`): a footprint of diameter D on a slope tan(theta) returns ground photons over
    +/- D/2 x tan(theta) around its centre, so the ground window is halfwidth_m + D/2 x slope. Without it (v0.1-v0.3) the
    window is a fixed halfwidth_m, which on slopes misses the upslope ground returns: the surface then sits too low and
    ground photons are labelled canopy (LOG, 17 Oct 2026). Across-track slope is unknown from one beam and not added."""
    gc = cfg["reclass"]["ground"]
    if not gc.get("slope_window", False):
        return np.full(np.shape(slope), float(gc["halfwidth_m"]))
    return gc["halfwidth_m"] + cfg["icesat2"]["footprint_diameter_m"] / 2.0 * np.abs(np.nan_to_num(slope))


def lowest_dense_layer(hs, bs, n_bins, thickness, frac, min_n=3):
    """v0.5 first ground guess per along-track bin: the median height of the LOWEST layer (`thickness` m thick) that holds
    at least `frac` x the photons of the bin's densest layer (and >= min_n photons); NaN where none.

    v0.1-v0.4 started from a low percentile of all signal photons (lower envelope). Photons a few metres below the
    surface that pass the noise filter (detector after-pulses under bright or specular surfaces such as water, daytime
    background clusters) pulled that envelope down; the iterations then kept the surface metres too low and called
    the true surface canopy (LOG 17 Oct 2026, v0.5). Such photons are sparse next to the surface return, so the lowest
    layer with at least half the densest layer's photons is the surface. hs, bs: signal photon heights and bin indices.

    min_n: v0.5 also required >= 3 photons in the layer. Under dense tall canopy a 10 m bin often holds only 1-2 ground
    photons, so the layer test skipped the ground and started on a canopy layer: the ground rose > 1 m in 8-15 % of
    CanElevation segments >= 10 m and tall forest came out ~0.5 m shorter than v0.4 (LOG 17 Oct 2026). v0.6
    (`ground.dense_min_photons: 1`) keeps only the fraction test."""
    out = np.full(n_bins, np.nan)
    order = np.lexsort((hs, bs))
    hs, bs = np.asarray(hs, float)[order], np.asarray(bs)[order]
    starts = np.searchsorted(bs, np.arange(n_bins))
    ends = np.searchsorted(bs, np.arange(n_bins), side="right")
    for b in range(n_bins):
        h = hs[starts[b]:ends[b]]
        if len(h) < min_n:
            continue
        n = np.searchsorted(h, h + thickness, side="right") - np.arange(len(h))   # photons in [h_i, h_i + thickness]
        ok = np.flatnonzero((n >= frac * n.max()) & (n >= min_n))
        if len(ok):
            i = ok[0]
            out[b] = np.median(h[i:i + n[i]])
    return out


def ground_surface(x, h, signal, cfg, return_slope=False):
    """Step 2. Ground surface from the lower envelope of signal photons (v0.5 `ground.start: lowest_dense_layer`: from the
    lowest dense layer, see lowest_dense_layer), refined iteratively.
    Returns the surface height at every photon and the along-track ground spread (robust sigma); with
    return_slope=True also the along-track ground slope (m/m) at every photon."""
    gc = cfg["reclass"]["ground"]
    edges = np.arange(np.floor(x.min()), x.max() + gc["bin_m"], gc["bin_m"])
    centers = 0.5 * (edges[:-1] + edges[1:])
    b = np.clip(np.digitize(x, edges) - 1, 0, len(centers) - 1)
    xs, hs, bs = x[signal], h[signal], b[signal]
    if len(xs) < 3:
        nan = np.full_like(h, np.nan, dtype=float)
        return (nan, nan.copy(), nan.copy()) if return_slope else (nan, nan.copy())
    if gc.get("start", "envelope") == "lowest_dense_layer":
        # v0.5: first guess = lowest dense layer, so stray photons below the surface cannot pull the ground down
        surf_bins = lowest_dense_layer(hs, bs, len(centers), 2 * gc["halfwidth_m"], gc["dense_frac"],
                                       gc.get("dense_min_photons", 3))
    else:
        df = pd.DataFrame({"b": bs, "h": hs})
        env = df.groupby("b")["h"].quantile(gc["envelope_pct"] / 100.0)
        surf_bins = np.full(len(centers), np.nan)
        surf_bins[env.index.to_numpy()] = env.to_numpy()
    sigma_bins = np.full(len(centers), np.nan)
    for _ in range(gc["n_iter"]):
        valid = np.isfinite(surf_bins)
        if valid.sum() < 2:
            break
        filled = np.interp(centers, centers[valid], surf_bins[valid])
        filled = _rolling_median(filled, gc["smooth_bins"])
        surf_ph = np.interp(xs, centers, filled)
        slope_ph = np.interp(xs, centers, np.gradient(filled, centers)) if len(centers) > 1 else np.zeros(len(xs))
        near = np.abs(hs - surf_ph) <= ground_halfwidth(slope_ph, cfg)
        if near.sum() < 3:
            break
        d = pd.DataFrame({"b": bs[near], "r": hs[near] - surf_ph[near]})
        med = d.groupby("b")["r"].median()
        mad = d.groupby("b")["r"].apply(lambda r: 1.4826 * np.median(np.abs(r - np.median(r))))
        surf_bins = np.full(len(centers), np.nan)
        surf_bins[med.index.to_numpy()] = filled[med.index.to_numpy()] + med.to_numpy()
        sigma_bins = np.full(len(centers), np.nan)
        sigma_bins[mad.index.to_numpy()] = mad.to_numpy()
    valid = np.isfinite(surf_bins)
    if valid.sum() < 2:
        nan = np.full_like(h, np.nan, dtype=float)
        return (nan, nan.copy(), nan.copy()) if return_slope else (nan, nan.copy())
    filled = _rolling_median(np.interp(centers, centers[valid], surf_bins[valid]), gc["smooth_bins"])
    sv = np.isfinite(sigma_bins)
    sig = np.interp(centers, centers[sv], sigma_bins[sv]) if sv.sum() >= 2 else np.full(len(centers), gc["halfwidth_m"] / 2)
    if return_slope:
        return np.interp(x, centers, filled), np.interp(x, centers, sig), np.interp(x, centers, np.gradient(filled, centers))
    return np.interp(x, centers, filled), np.interp(x, centers, sig)


def canopy_column_top(x, relief, background_rate, min_rel, cfg):
    """v0.2 canopy test for sparse canopy photons: per along-track column, the height up to which photons above the
    ground clearly outnumber the solar background expected in that height range.

    Tall, open canopy spreads few photons over tens of metres, so a small box around each photon (step 1) often holds
    fewer neighbours than its threshold and real canopy photons are dropped. Here the photons above the ground in a
    column (window_along_m long) are sorted by relief; for each candidate top z the excess is N(z) - mu(z), where
    mu(z) = background rate x 2/c x shots x (z - min_rel) is the expected background count between min_rel and z.
    The top is the z with the largest excess, accepted if (N - mu) / sqrt(mu + 1) >= k_sigma and N >= min_photons.
    Photons are not counted across a vertical gap larger than max_gap_m (stray photons high above the canopy).
    Only instrument quantities (background rate, shot spacing) and the Poisson test are used, so it adapts to
    day/night and beam strength. Returns the column top (relief, m) at every photon; NaN where no canopy is found."""
    col = cfg["reclass"]["canopy"]["column"]
    L = col["window_along_m"]
    per_m_shot = np.asarray(background_rate, float) * 2.0 / C_LIGHT        # background photons per m height per shot
    shots = L / cfg["icesat2"]["shot_spacing_m"]
    top = np.full(len(x), np.nan)
    b = np.floor((x - x.min()) / L).astype(np.int64)
    above = np.isfinite(relief) & (relief > min_rel) & (relief <= cfg["reclass"]["canopy"]["max_relief_m"])
    for k in np.unique(b):
        inb = b == k
        r = np.sort(relief[inb & above])
        if len(r) < col["min_photons"]:
            continue
        lo = float(np.median(np.atleast_1d(min_rel)[inb])) if np.ndim(min_rel) else float(min_rel)
        gaps = np.diff(r)
        cut = np.where(gaps > col["max_gap_m"])[0]
        if len(cut):
            r = r[:cut[0] + 1]
        n = np.arange(1, len(r) + 1)
        mu = float(np.median(per_m_shot[inb])) * shots * np.clip(r - lo, 0, None)
        excess = n - mu
        j = int(np.argmax(excess))
        if n[j] >= col["min_photons"] and excess[j] / np.sqrt(mu[j] + 1.0) >= col["k_sigma"]:
            if col.get("top_rule", "max") == "plateau":
                # v0.3: above the real canopy the excess only wanders with the background (a random walk), so its
                # maximum drifts upward when the background is high. Take the lowest height whose excess is within
                # top_k standard deviations of the background fluctuation between it and the maximum.
                tol = col.get("top_k", 2.0) * np.sqrt(np.clip(mu[j] - mu[: j + 1], 0, None))   # 0 when no background
                j = int(np.argmax(excess[: j + 1] >= excess[j] - tol))
            top[inb] = r[j]
    return top


def classify_track(x, h, background_rate, cfg, extra=False):
    """Steps 1-3 for one granule x beam track. Returns (class, relief, signal, ground_sigma); with extra=True also a
    dict with the per-photon canopy floor (relief above which a photon can be canopy, m) and ground slope (m/m)."""
    cc = cfg["reclass"]["canopy"]
    gc = cfg["reclass"]["ground"]
    order = np.argsort(x)
    inv = np.empty_like(order)
    inv[order] = np.arange(len(order))
    x, h, br = np.asarray(x, float)[order], np.asarray(h, float)[order], np.asarray(background_rate, float)[order]

    signal, _, _ = noise_filter(x, h, br, cfg)
    surf, gsig, slope = ground_surface(x, h, signal, cfg, return_slope=True)
    relief = h - surf
    hw = ground_halfwidth(slope, cfg)                       # = halfwidth_m unless ground.slope_window (v0.4)
    cls = np.zeros(len(h), dtype=np.int8)
    cls[signal & (np.abs(relief) <= hw)] = 1
    # canopy starts above the ground spread; v0.4 adds the slope part of the ground window (0 on flat ground)
    min_rel = np.maximum(cc["min_relief_m"], cc["ground_sigma_k"] * np.nan_to_num(gsig, nan=0.0)) + (hw - gc["halfwidth_m"])
    cls[signal & (relief > min_rel) & (relief <= cc["max_relief_m"])] = 2
    if cc.get("column", {}).get("enabled", False):
        # v0.2: photons above the ground and below the column canopy top are canopy even if the box filter missed them
        ctop = canopy_column_top(x, relief, br, min_rel, cfg)
        cls[(cls == 0) & (relief > min_rel) & (relief <= ctop)] = 2

    if cc["toc_recovery"]:
        # canopy envelope: rolling max of canopy relief along track
        can = cls == 2
        if can.sum() > 0:
            s = pd.Series(np.where(can, relief, np.nan), index=x)
            env = s.rolling(window=int(max(3, cc["toc_window_m"] / 0.7)), center=True, min_periods=1).max().to_numpy()
            cand = (~signal) & (relief > min_rel) & (relief <= np.nan_to_num(env, nan=-1) + cc["toc_max_above_m"]) \
                   & (relief > np.nan_to_num(env, nan=np.inf) - 1.0) & (relief <= cc["max_relief_m"])
            if cand.any():
                xc = x[cand]
                tree = cKDTree(xc[:, None])
                nn = tree.query_ball_point(xc[:, None], r=cc["toc_window_m"], return_length=True) - 1
                need = np.full(len(xc), float(cc["toc_min_neighbours"]))
                if "toc_k_sigma" in cc:
                    # v0.3: neighbours must clearly exceed the background expected in the candidate window
                    # (+/- toc_window_m along track, toc window height), as in the noise filter. In daytime over
                    # bright surfaces ~2 noise photons fall in that window by chance, which v0.1/v0.2 accepted.
                    win_h = cc["toc_max_above_m"] + 1.0
                    lam = br[cand] * 2.0 * win_h / C_LIGHT * (2 * cc["toc_window_m"] / cfg["icesat2"]["shot_spacing_m"])
                    need = np.maximum(need, lam + cc["toc_k_sigma"] * np.sqrt(lam))
                idx = np.where(cand)[0][nn >= need]
                cls[idx] = 3
    if extra:
        return cls[inv], relief[inv], signal[inv], gsig[inv], {"canopy_floor": min_rel[inv], "ground_slope": slope[inv]}
    return cls[inv], relief[inv], signal[inv], gsig[inv]


def reclassify(photons, cfg):
    """Apply the reclassifier to every track. Adds class_new, relief_new, signal_new, ground_sigma_new."""
    photons = photons.copy()
    n = len(photons)
    cls_all = np.zeros(n, dtype="int8")
    rel_all = np.full(n, np.nan)
    sig_all = np.zeros(n, dtype=bool)
    gs_all = np.full(n, np.nan)
    floor_all = np.full(n, np.nan)
    slope_all = np.full(n, np.nan)
    pos = pd.Series(np.arange(n), index=photons.index)
    for _, idx in photons.groupby("track_id").groups.items():
        sub = photons.loc[idx]
        if len(sub) < 10:
            continue
        cls, rel, sig, gs, ex = classify_track(sub["x_atc"].to_numpy(), sub["height"].to_numpy(),
                                               sub["background_rate"].to_numpy(), cfg, extra=True)
        p = pos.loc[idx].to_numpy()
        cls_all[p], rel_all[p], sig_all[p], gs_all[p] = cls, rel, sig, gs
        floor_all[p], slope_all[p] = ex["canopy_floor"], ex["ground_slope"]
    photons["class_new"], photons["relief_new"] = cls_all, rel_all
    photons["signal_new"], photons["ground_sigma_new"] = sig_all, gs_all
    photons["canopy_floor_new"], photons["ground_slope_new"] = floor_all, slope_all
    return photons


def native_relief(photons, cfg):
    """Relief of every photon above a ground surface interpolated from ATL08 ground photons, using the
    same smoothing as the new classifier, so native and new segments differ only in classification."""
    photons = photons.copy()
    photons["relief_atl08"] = np.nan
    gc = cfg["reclass"]["ground"]
    for _, idx in photons.groupby("track_id").groups.items():
        sub = photons.loc[idx].sort_values("x_atc")
        g = sub[sub["atl08_class"] == 1]
        if len(g) < 2:
            continue
        edges = np.arange(np.floor(sub["x_atc"].min()), sub["x_atc"].max() + gc["bin_m"], gc["bin_m"])
        centers = 0.5 * (edges[:-1] + edges[1:])
        b = np.clip(np.digitize(g["x_atc"], edges) - 1, 0, len(centers) - 1)
        med = pd.Series(g["height"].to_numpy()).groupby(b).median()
        surf = np.interp(centers, centers[med.index.to_numpy()], med.to_numpy())
        photons.loc[sub.index, "relief_atl08"] = sub["height"].to_numpy() - np.interp(sub["x_atc"], centers, surf)
    return photons


# ============================================================ 30 m segments

def _pct(v, q):
    return np.percentile(v, q) if len(v) else np.nan


def _shots_in_segment(ph, edge, cfg):
    """Laser shots in a 30 m segment, including shots that returned no photon.

    v0.1 counted distinct shot ids among the photons, which misses empty shots and inflates per-shot rates where
    returns are sparse (weak beams, dense canopy, night). With `segments.shots_from_length` (v0.2): a full segment
    has length / shot_spacing shots; the first and last segment of a track can be partial, so there the count comes
    from the photon time span at the pulse rate (capped at the full-segment count)."""
    ic, seg = cfg["icesat2"], cfg["segments"]
    if not seg.get("shots_from_length", False):
        return ph["shot"].nunique() if "shot" in ph else max(1, int(np.ptp(ph["x_atc"]) / ic["shot_spacing_m"]))
    full = int(round(seg["length_m"] / ic["shot_spacing_m"]))
    if not edge:
        return full
    if "time_ns" in ph:
        t = pd.to_datetime(ph["time_ns"]).astype("int64").to_numpy()
        n = int(round(np.ptp(t) * 1e-9 * ic["pulse_rate_hz"])) + 1
    else:
        n = int(round(np.ptp(ph["x_atc"]) / ic["shot_spacing_m"])) + 1
    return int(np.clip(n, 1, full))


def _segments_table(photons, cfg, class_col, relief_col):
    """Vectorised core of segment_metrics: one row per (track_id, seg) with the same quantities as the per-segment loop."""
    seg, ic = cfg["segments"], cfg["icesat2"]
    L = seg["length_m"]
    gh = cfg["reclass"]["ground"]["halfwidth_m"]
    keys = ["track_id", "seg"]
    p = photons[np.isfinite(photons[relief_col])] if relief_col in photons else photons
    if not len(p):
        return pd.DataFrame()
    cols = [c for c in ["track_id", "x_atc", "lon", "lat", "height", "background_rate", "solar_elevation", "rgt", "cycle",
                        "gt", "spot", "strong", "granule", "year", "doy", "shot", "time_ns",
                        "segment_snowcover", "segment_landcover", "msw_flag", "atl03_cnf"] if c in p]
    d = p[cols].copy()
    d["cls"] = p[class_col].to_numpy()
    d["rel"] = p[relief_col].to_numpy()
    d["seg"] = np.floor(d["x_atc"].to_numpy() / L).astype(np.int64)
    d = d.sort_values(["track_id", "seg", "x_atc"], kind="mergesort")
    can, gr = d["cls"].isin((2, 3)), d["cls"].eq(1)
    g = d.groupby(keys, sort=True)
    out = pd.DataFrame({"n_canopy": can.groupby([d.track_id, d.seg]).sum(), "n_ground": gr.groupby([d.track_id, d.seg]).sum(),
                        "n_noise": d["cls"].eq(0).groupby([d.track_id, d.seg]).sum()})
    out.index.names = keys
    first = g[["rgt", "cycle", "gt", "spot", "strong"] + (["granule"] if "granule" in d else []) + ["year", "doy"]].first()
    out = out.join(first)
    out["x_atc"] = g["x_atc"].mean(); out["lon"] = g["lon"].mean(); out["lat"] = g["lat"].mean()
    out[["lon0", "lat0"]] = g[["lon", "lat"]].first().to_numpy()
    out[["lon1", "lat1"]] = g[["lon", "lat"]].last().to_numpy()
    out["solar_elevation"] = g["solar_elevation"].median()
    out["background_rate"] = g["background_rate"].median()
    out = out[(out.n_canopy + out.n_ground) >= seg["min_photons"]]
    # shots per segment
    full = int(round(L / ic["shot_spacing_m"]))
    if seg.get("shots_from_length", False):
        lim = d.groupby("track_id")["seg"].agg(["min", "max"])
        tr = out.index.get_level_values(0); sg = out.index.get_level_values(1)
        edge = (sg == lim.loc[tr, "min"].to_numpy()) | (sg == lim.loc[tr, "max"].to_numpy())
        if "time_ns" in d:
            t = pd.to_datetime(d["time_ns"]).astype("int64")
            span = t.groupby([d.track_id, d.seg]).agg(lambda v: v.max() - v.min()).reindex(out.index).to_numpy() * 1e-9
            n_edge = np.round(span * ic["pulse_rate_hz"]).astype(int) + 1
        else:
            span = g["x_atc"].agg(lambda v: v.max() - v.min()).reindex(out.index).to_numpy()
            n_edge = np.round(span / ic["shot_spacing_m"]).astype(int) + 1
        out["n_shots"] = np.where(edge, np.clip(n_edge, 1, full), full)
    else:
        if "shot" in d:
            out["n_shots"] = g["shot"].nunique().reindex(out.index)
        else:
            out["n_shots"] = np.maximum(1, (g["x_atc"].agg(lambda v: v.max() - v.min()).reindex(out.index) / ic["shot_spacing_m"]).astype(int))
    # heights
    dc = d[can]
    gc = dc.groupby(keys)["rel"]
    pcts = sorted(set(seg["rh_percentiles"]) | {98, 100})
    rh_cols = [f"rh{p}" for p in pcts]
    if len(dc):
        q = gc.quantile([x / 100 for x in pcts]).unstack()
        q.columns = [f"rh{int(round(c * 100))}" for c in q.columns]
    else:                                   # no canopy photon in any segment (e.g. bare tundra with ATL08 classes)
        q = pd.DataFrame(index=out.index, columns=rh_cols, dtype=float)
    out = out.join(q.reindex(columns=rh_cols))
    out["h_canopy"] = out["rh98"]; out["h_max_canopy"] = out["rh100"]
    out["h_mean_canopy"] = gc.mean().reindex(out.index)
    out["h_te_median"] = d[gr].groupby(keys)["height"].median().reindex(out.index)
    sig = pd.concat([d.loc[gr, keys].assign(rel=d.loc[gr, "rel"].clip(lower=0)), dc[keys + ["rel"]]])
    qg = sig.groupby(keys)["rel"].quantile([x / 100 for x in seg["rh_percentiles"]]).unstack()
    qg.columns = [f"rh{int(round(c * 100))}_gedi" for c in qg.columns]
    out = out.join(qg)
    if 100 not in seg["rh_percentiles"]:
        out = out.drop(columns=["rh100"])
    if 98 not in seg["rh_percentiles"]:
        out = out.drop(columns=["rh98"])
    # photon rates
    noise_per_m_shot = out["background_rate"] * 2 / C_LIGHT
    can_window = (gc.max().reindex(out.index) - gh).fillna(0.0)
    out["Evr"] = out["n_canopy"] / out["n_shots"]
    out["Egr"] = out["n_ground"] / out["n_shots"]
    out["Ev"] = np.maximum(out["Evr"] - noise_per_m_shot * np.maximum(can_window, 0), 0.0)
    out["Eg"] = np.maximum(out["Egr"] - noise_per_m_shot * 2 * gh, 0.0)
    for c in ("segment_snowcover", "segment_landcover", "msw_flag", "atl03_cnf"):
        if c in d:
            cnt = d.groupby(keys + [c]).size().reset_index(name="k").sort_values(keys + ["k", c], ascending=[True, True, False, True])
            out[c] = cnt.drop_duplicates(keys).set_index(keys)[c].reindex(out.index)
    out = out.reset_index()
    for c in ("n_canopy", "n_ground", "n_noise", "n_shots"):
        out[c] = out[c].astype(int)
    return out


def vegetation_presence(photons, segs, cfg, relief_col="relief_new"):
    """v0.4: is there vegetation above the ground in each 30 m segment, and could it have been seen?

    Presence: ALL photons of the segment (any class, so the test does not depend on how the noise filter and canopy
    rules labelled them) with relief between the canopy floor and max_relief_m are sorted by relief. For each height z,
    excess(z) = N(z) - mu(z), with mu(z) = background rate x 2/c x shots x (z - floor) the solar background expected
    between the floor and z. presence_sigma = max over z of excess / sqrt(mu + 1) (Poisson); vegetation is present if
    it is >= k_sigma. Only instrument quantities, as in the noise filter and the column test.

    Detectability: a canopy covering min_cover of the footprint with canopy/ground reflectance ratio min_ratio returns
    about Ng x min_ratio x c / (1 - c) photons for Ng ground photons (Purslow et al. 2023, Eq. 1-2). It would have been
    seen if that number is >= k_sigma x sqrt(mu_layer + 1), mu_layer being the background in the lowest layer_m above
    the floor. Returns presence_sigma, presence_top_m (z of the maximum), veg_present, veg_detectable, ground_slope_deg."""
    pc = cfg["reclass"]["short_veg"]["presence"]
    L = cfg["segments"]["length_m"]
    keys = ["track_id", "seg"]
    p = photons[np.isfinite(photons[relief_col])]
    floor = p["canopy_floor_new"].to_numpy() if "canopy_floor_new" in p else np.full(len(p), cfg["reclass"]["canopy"]["min_relief_m"])
    d = pd.DataFrame({"track_id": p["track_id"].to_numpy(), "seg": np.floor(p["x_atc"].to_numpy() / L).astype(np.int64),
                      "rel": p[relief_col].to_numpy(), "floor": floor,
                      "slope": p["ground_slope_new"].to_numpy() if "ground_slope_new" in p else np.zeros(len(p))})
    s = segs.set_index(keys)[["n_shots", "background_rate", "ground_signal_photons"]].copy()
    g = d.groupby(keys)
    s["floor"] = g["floor"].median().reindex(s.index)
    s["ground_slope_deg"] = np.degrees(np.arctan(g["slope"].median().abs())).reindex(s.index)
    per_m = s["background_rate"] * 2.0 / C_LIGHT * s["n_shots"]                 # background photons per m of height
    a = d.join(s[["floor"]].rename(columns={"floor": "sfloor"}), on=keys).join(per_m.rename("per_m"), on=keys)
    a = a[(a["rel"] > a["sfloor"]) & (a["rel"] <= cfg["reclass"]["canopy"]["max_relief_m"])].sort_values(keys + ["rel"])
    a["N"] = a.groupby(keys).cumcount() + 1
    a["mu"] = a["per_m"] * (a["rel"] - a["sfloor"])
    a["S"] = (a["N"] - a["mu"]) / np.sqrt(a["mu"] + 1.0)
    if len(a):
        best = a.loc[a.groupby(keys)["S"].idxmax(), keys + ["S", "rel"]].set_index(keys)
        s["presence_sigma"] = best["S"].reindex(s.index).fillna(0.0)
        s["presence_top_m"] = best["rel"].reindex(s.index)
    else:
        s["presence_sigma"], s["presence_top_m"] = 0.0, np.nan
    s["veg_present"] = s["presence_sigma"] >= pc["k_sigma"]
    c = pc["min_cover"]
    expected = s["ground_signal_photons"] * pc["min_ratio"] * c / (1.0 - c)
    s["veg_detectable"] = expected >= pc["k_sigma"] * np.sqrt(per_m * pc["layer_m"] + 1.0)
    cols = ["presence_sigma", "presence_top_m", "veg_present", "veg_detectable", "ground_slope_deg"]
    return segs.join(s[cols], on=keys)


def segment_metrics(photons, cfg, class_col="class_new", relief_col="relief_new", scheme="new", fast=None):
    """30 m along-track segments from classified photons (one row per track x segment).

    Canopy-only RH (ATL08 style: rh{p} of canopy-photon relief) and GEDI-style RH over ground + canopy
    photons (Purslow et al. 2023, Sec. 2.3.3; ground photons enter at their relief). Photon rates per shot
    are background-corrected with the ATL03 background rate (expected noise in each class window), a
    simplification of Purslow et al. Sec. 2.2 that does not need the telemetry window length."""
    seg = cfg["segments"]
    L = seg["length_m"]
    gh = cfg["reclass"]["ground"]["halfwidth_m"]
    sv = cfg["reclass"]["short_veg"]
    # vectorised by default (same numbers as the per-segment loop, verified 16 Oct 2026); fast=False for the loop
    fast = cfg["segments"].get("vectorized", True) if fast is None else fast
    if fast:
        out = _segments_table(photons, cfg, class_col, relief_col)
        if len(out):
            out.insert(2, "scheme", scheme)
    else:
        rows = []
        canopy_classes = (2, 3)
        for tid, sub in photons.groupby("track_id"):
            sub = sub[np.isfinite(sub[relief_col])] if relief_col in sub else sub
            if not len(sub):
                continue
            sid = np.floor(sub["x_atc"].to_numpy() / L).astype(np.int64)
            s_first, s_last = sid.min(), sid.max()
            for s, ph in sub.groupby(sid):
                cls = ph[class_col].to_numpy()
                rel = ph[relief_col].to_numpy()
                can = np.isin(cls, canopy_classes)
                gr = cls == 1
                if (can.sum() + gr.sum()) < seg["min_photons"]:
                    continue
                n_shots = _shots_in_segment(ph, s in (s_first, s_last), cfg)
                br = float(ph["background_rate"].median())
                noise_per_m_shot = br * 2 / C_LIGHT
                can_rel = rel[can]
                h_can = _pct(can_rel, 98)
                can_window = (np.nanmax(can_rel) - gh) if can.any() else 0.0
                r = {"track_id": tid, "seg": int(s), "scheme": scheme,
                     "rgt": ph["rgt"].iat[0], "cycle": ph["cycle"].iat[0], "gt": ph["gt"].iat[0],
                     "spot": ph["spot"].iat[0], "strong": bool(ph["strong"].iat[0]),
                     "granule": ph["granule"].iat[0] if "granule" in ph else None,
                     "x_atc": float(ph["x_atc"].mean()), "lon": float(ph["lon"].mean()), "lat": float(ph["lat"].mean()),
                     "lon0": float(ph.loc[ph["x_atc"].idxmin(), "lon"]), "lat0": float(ph.loc[ph["x_atc"].idxmin(), "lat"]),
                     "lon1": float(ph.loc[ph["x_atc"].idxmax(), "lon"]), "lat1": float(ph.loc[ph["x_atc"].idxmax(), "lat"]),
                     "year": int(ph["year"].iat[0]), "doy": int(ph["doy"].iat[0]),
                     "solar_elevation": float(ph["solar_elevation"].median()), "background_rate": br,
                     "n_shots": n_shots, "n_ground": int(gr.sum()), "n_canopy": int(can.sum()),
                     "n_noise": int((cls == 0).sum()),
                     "h_te_median": float(np.median(ph["height"].to_numpy()[gr])) if gr.any() else np.nan,
                     "h_canopy": h_can, "h_max_canopy": _pct(can_rel, 100), "h_mean_canopy": float(np.mean(can_rel)) if can.any() else np.nan}
                for p in seg["rh_percentiles"]:
                    r[f"rh{p}"] = _pct(can_rel, p)
                sig_rel = np.concatenate([np.clip(rel[gr], 0, None), can_rel])
                for p in seg["rh_percentiles"]:
                    r[f"rh{p}_gedi"] = _pct(sig_rel, p)
                r["Evr"] = can.sum() / n_shots
                r["Egr"] = gr.sum() / n_shots
                r["Ev"] = max(r["Evr"] - noise_per_m_shot * max(can_window, 0), 0.0)
                r["Eg"] = max(r["Egr"] - noise_per_m_shot * 2 * gh, 0.0)
                for c in ("segment_snowcover", "segment_landcover", "msw_flag", "atl03_cnf"):
                    if c in ph:
                        r[c] = ph[c].mode().iat[0]
                rows.append(r)
        out = pd.DataFrame(rows)
    if not len(out):
        return out
    out["canopy_signal_photons"] = out["Ev"] * out["n_shots"]
    out["ground_signal_photons"] = out["Eg"] * out["n_shots"]
    if scheme == "new" and "presence" in sv:
        # v0.4: one decision from one test (vegetation_presence). Vegetation present -> a height (NaN if too few
        # canopy photons to place RH98: present but not measurable). Not present and a canopy would have been seen ->
        # 0 m. Not present and it could not have been seen, or too little signal overall -> NaN (low_signal).
        out = vegetation_presence(photons, out, cfg, relief_col)
        ls = sv["low_signal"]
        enough = (out["canopy_signal_photons"] + out["ground_signal_photons"]) >= ls["min_signal_photons"]
        present, detect = out["veg_present"], out["veg_detectable"]
        measurable = (out["n_canopy"] >= sv["min_canopy_photons"]) & out["h_canopy"].notna()
        out["h_canopy_raw"] = out["h_canopy"]
        out["short_veg_flag"] = enough & ~present & detect                         # 0 m: vegetation demonstrably absent
        out["veg_unmeasured"] = enough & present & ~measurable                    # vegetation seen, height not measurable
        out["low_signal"] = ~enough | (~present & ~detect)
        out.loc[out["short_veg_flag"], "h_canopy"] = 0.0
        out.loc[present & measurable & (out["h_canopy"] < sv["min_resolvable_m"]), "h_canopy"] = 0.0
        out.loc[out["low_signal"] | out["veg_unmeasured"], "h_canopy"] = np.nan
    elif scheme == "new" and "low_signal" in sv:
        # v0.2: no height where the segment has too little signal to tell bare ground from canopy (NaN, flagged);
        # 0 m only where there is enough signal and the canopy evidence is weak or below the resolvable height.
        ls = sv["low_signal"]
        signal = out["canopy_signal_photons"] + out["ground_signal_photons"]
        out["low_signal"] = signal < ls["min_signal_photons"]
        weak_canopy = ((out["n_canopy"] < sv["min_canopy_photons"]) | out["h_canopy"].isna()
                       | (out["canopy_signal_photons"] < sv.get("min_canopy_signal_photons", 0)))
        out["short_veg_flag"] = ~out["low_signal"] & (weak_canopy | (out["h_canopy"] < sv["min_resolvable_m"]))
        out["h_canopy_raw"] = out["h_canopy"]
        out.loc[out["short_veg_flag"], "h_canopy"] = 0.0
        out.loc[out["low_signal"], "h_canopy"] = np.nan
    elif scheme == "new":
        out["short_veg_flag"] = ((out["n_canopy"] < sv["min_canopy_photons"]) | (out["h_canopy"] < sv["min_resolvable_m"])
                                 | out["h_canopy"].isna() | (out["canopy_signal_photons"] < sv.get("min_canopy_signal_photons", 0)))
        out["h_canopy_raw"] = out["h_canopy"]
        out.loc[out["short_veg_flag"], "h_canopy"] = 0.0
    return gpd.GeoDataFrame(out, geometry=gpd.points_from_xy(out["lon"], out["lat"]), crs="EPSG:4326")


# ============================================================ canopy cover (Purslow et al. 2023)

def fit_reflectance_ratio(segs, cfg, track_col="track_id"):
    """Canopy:ground reflectance ratio rho_v/rho_g from background-corrected photon rates.

    Orthogonal least squares of Ev on Eg with one slope shared by all tracks (slope = -rho_v/rho_g) and a
    free intercept per track (Ev at 100% cover; varies with atmospheric transmission). Each track is
    weighted by Pearson r^2 of Ev vs Eg (Purslow et al. 2023, Sec. 2.2; Armston et al. 2013).
    Returns dict(ratio, slope, tracks=DataFrame[track, n, r2, Ev100, Eg0, used])."""
    cv = cfg["cover"]
    d = segs[[track_col, "Ev", "Eg"]].dropna()
    stats = []
    for t, g in d.groupby(track_col):
        r = np.corrcoef(g["Eg"], g["Ev"])[0, 1] if len(g) > 2 and g["Eg"].std() > 0 and g["Ev"].std() > 0 else np.nan
        stats.append({"track": t, "n": len(g), "r": r})
    st = pd.DataFrame(stats)
    use = st[(st["n"] >= cv["min_segments_per_track"]) & (st["r"] < 0)].copy()   # cover trade-off -> negative r
    use["w"] = use["r"] ** 2
    if len(use) < 1:
        return {"ratio": np.nan, "slope": np.nan, "tracks": st.assign(used=False)}
    tracks = use["track"].tolist()
    dd = d[d[track_col].isin(tracks)]
    ti = dd[track_col].map({t: i for i, t in enumerate(tracks)}).to_numpy()
    w = dd[track_col].map(dict(zip(use["track"], use["w"]))).to_numpy()
    x, y = dd["Eg"].to_numpy(), dd["Ev"].to_numpy()
    a0 = np.array([max(y[ti == i].max(), 0.1) for i in range(len(tracks))])

    def resid(p):
        m, a = p[0], p[1:]
        return np.sqrt(w) * (y - a[ti] - m * x) / np.sqrt(1 + m * m)

    sol = least_squares(resid, np.concatenate([[-1.0], a0]), method="lm")
    m, a = sol.x[0], sol.x[1:]
    use["Ev100"] = a
    use["Eg0"] = -a / m if m != 0 else np.nan
    use["used"] = (use["Ev100"] > cv["min_rate_per_shot"]) & (use["Eg0"] > cv["min_rate_per_shot"])
    st = st.merge(use[["track", "w", "Ev100", "Eg0", "used"]], on="track", how="left")
    st["used"] = st["used"].fillna(False)
    if st["used"].sum() and st["used"].sum() < len(tracks):   # refit on the tracks that pass the rate filter
        sub = segs[segs[track_col].isin(st.loc[st["used"], "track"])]
        return fit_reflectance_ratio(sub, cfg, track_col) | {"tracks_all": st}
    return {"ratio": float(-m), "slope": float(m), "tracks": st}


def canopy_cover(n_canopy, n_ground, ratio):
    """cv = 1 / (1 + (rho_v/rho_g) * Ng / Nv)   (Ni-Meister et al. 2001; Armston et al. 2013; Purslow et al. 2023 eq. 1)."""
    nv = np.asarray(n_canopy, float)
    ng = np.asarray(n_ground, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        cv = 1.0 / (1.0 + ratio * ng / nv)
    cv = np.where(nv <= 0, 0.0, cv)
    return np.where((nv + ng) <= 0, np.nan, cv)


# ============================================================ helpers

def track_profile(photons, track_id, x0=None, length=None):
    """Photons of one track, optionally a window [x0, x0 + length] of along-track distance (m)."""
    p = photons[photons["track_id"] == track_id].sort_values("x_atc")
    if x0 is not None:
        p = p[(p["x_atc"] >= x0) & (p["x_atc"] <= x0 + (length or 1e9))]
    return p


# ============================================================ production (one tile x one year)

def granule_parts(name):
    """ATL03_YYYYMMDDhhmmss_RRRRCCSS_VVV_RR.h5 -> (rgt, cycle, region)."""
    p = name.split("_")[2]
    return int(p[0:4]), int(p[4:6]), int(p[6:8])


def process_tile(tile_geom, tile_num, year, cfg, out_dir, months=None, spots=None, write_photons=False):
    """Reclassified 30 m segments for one tile and year, in the schema of our v7 files plus new columns.
    One SlideRule request per granule (failures are logged and skipped). Returns (segments, log)."""
    months = months or cfg["icesat2"]["months"]
    granules = granules_from_cmr(tile_geom, [year], months, release=cfg["icesat2"]["release"])
    log, frames = [], []
    for g in granules:
        ph = fetch_photons(tile_geom, [g], cfg)
        if spots is not None and len(ph):
            ph = ph[ph["spot"].isin(spots)]
        log.append({"granule": g, "n_photons": len(ph)})
        if not len(ph):
            continue
        ph = reclassify(ph, cfg)
        seg = segment_metrics(ph, cfg)
        if len(seg):
            frames.append(seg)
        if write_photons:
            write_parquet(ph, Path(out_dir) / "photons" / f"{tile_num:07d}_{g.replace('.h5', '')}.parquet",
                          provenance(cfg, granule=g))
    log = pd.DataFrame(log)
    if not frames:
        return gpd.GeoDataFrame(), log
    segs = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    segs = segs[segs.within(tile_geom)] if tile_geom is not None else segs
    segs["tile_num"] = tile_num
    fn = Path(out_dir) / f"atl08_reclass_{cfg['icesat2']['release']}_030m_{year}_{min(months):02d}_{max(months):02d}_v{cfg['version']}_{tile_num:07d}.parquet"
    write_parquet(segs, fn, provenance(cfg, tile_num=tile_num, year=year, months=months,
                                       granules=granules, n_granules=len(granules)))
    return segs, log


def match_segments(a, b, cols, max_dist_m=20.0, suffix="_b"):
    """For each segment in a, the nearest segment in b on the same track (track_id) within max_dist_m.
    Adds b's `cols` with `suffix`. Both inputs need lon/lat geometry (EPSG:4326)."""
    utm = a.estimate_utm_crs()
    a2, b2 = a.to_crs(utm), b.to_crs(utm)
    out = []
    for tid, ga in a2.groupby("track_id"):
        gb = b2[b2["track_id"] == tid]
        if not len(gb):
            out.append(ga)
            continue
        j = gpd.sjoin_nearest(ga, gb[cols + ["geometry"]].rename(columns={c: c + suffix for c in cols}),
                              how="left", max_distance=max_dist_m, distance_col="match_dist_m")
        out.append(j[~j.index.duplicated()].drop(columns="index_right", errors="ignore"))
    return gpd.GeoDataFrame(pd.concat(out), crs=utm).to_crs(4326)
