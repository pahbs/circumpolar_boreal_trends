"""Reference data for validating ICESat-2 photon classes and 30 m segments.

- G-LiHT (LP DAAC, GLCHMT / GLDTMT v001): granule search in CMR, download, footprint-summarised
  ground and canopy-top surfaces, ALS metrics inside ICESat-2 segment footprints.
- Seward Peninsula 2024 field transects: UAV DSM/DTM, field point-intercept heights.
- Geolocation and vertical datum offset per ICESat-2 track (from ATL08 ground photons vs reference DTM).
- Disturbance screen (Hansen GFC loss year).

Raster products are kept in their native projection; points are transformed to it for sampling.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol
from rasterio.windows import Window
import requests
from rasterio.mask import mask as rio_mask
from rasterio.warp import Resampling
from scipy import ndimage
from shapely.geometry import LineString, Polygon, box

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"


# ============================================================ G-LiHT search and download

def _cmr_polygon(entry):
    if entry.get("polygons"):
        v = list(map(float, entry["polygons"][0][0].split()))
        return Polygon(list(zip(v[1::2], v[0::2])))
    if entry.get("boxes"):
        s, w, n, e = map(float, entry["boxes"][0].split())
        return box(w, s, e, n)
    return None


def glihit_search(bbox, short_name="GLCHMT", temporal=None, page_size=2000):
    """G-LiHT granules (one strip each) intersecting bbox=(w,s,e,n). Returns GeoDataFrame (EPSG:4326)
    with granule name, campaign stem, date, https and s3 URLs."""
    rows, page = [], 1
    while True:
        params = {"short_name": short_name, "bounding_box": ",".join(map(str, bbox)),
                  "page_size": page_size, "page_num": page}
        if temporal:
            params["temporal"] = temporal
        r = requests.get(CMR, params=params, timeout=120)
        r.raise_for_status()
        es = r.json()["feed"]["entry"]
        for e in es:
            https = [l["href"] for l in e["links"] if l["href"].startswith("https") and l["href"].lower().endswith(".tif")]
            s3 = [l["href"] for l in e["links"] if l["href"].startswith("s3://") and l["href"].lower().endswith(".tif")]
            name = e.get("producer_granule_id") or e["title"]
            rows.append({"granule": name, "stem": re.sub(r"_(CHM|DTM|DSM)$", "", name.split(f"{short_name}_")[-1]),
                         "time_start": e["time_start"][:10], "year": int(e["time_start"][:4]),
                         "https": https[0] if https else None, "s3": s3[0] if s3 else None,
                         "geometry": _cmr_polygon(e)})
        if len(es) < page_size:
            break
        page += 1
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def glihit_pairs(bbox, temporal=None):
    """CHM and DTM granules for the same strips, matched on the strip stem."""
    chm = glihit_search(bbox, "GLCHMT", temporal)
    dtm = glihit_search(bbox, "GLDTMT", temporal)
    if not len(chm) or not len(dtm):
        return gpd.GeoDataFrame()
    m = chm.merge(dtm[["stem", "https", "s3"]], on="stem", suffixes=("_chm", "_dtm"))
    return gpd.GeoDataFrame(m, geometry="geometry", crs="EPSG:4326")


def earthdata_login(credentials_ini=None):
    """Earthdata Login for earthaccess. Uses an .ini file with an [EarthData] section (any case; keys
    username/user/login and password/pass) if it exists, else ~/.netrc. Values are passed via environment
    variables for this process only and never printed."""
    import configparser
    import earthaccess
    ini = Path(os.path.expanduser(credentials_ini or "~/credentials.ini"))
    if ini.exists():
        cp = configparser.ConfigParser()
        cp.read(ini)
        sec = next((s for s in cp.sections() if s.lower() == "earthdata"), None)
        if sec:
            keys = {k.lower(): v for k, v in cp[sec].items()}
            user = next((keys[k] for k in ("username", "user", "login") if k in keys), None)
            pw = next((keys[k] for k in ("password", "pass") if k in keys), None)
            if user and pw:
                os.environ["EARTHDATA_USERNAME"], os.environ["EARTHDATA_PASSWORD"] = user, pw
                return earthaccess.login(strategy="environment")
    return earthaccess.login(strategy="netrc", persist=False)


def download(urls, dest_dir, credentials_ini=None):
    """Download Earthdata files (https) with earthaccess (Earthdata Login: see earthdata_login).
    Existing files are skipped. Returns local paths in input order."""
    import earthaccess
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    todo = [u for u in urls if u and not (dest_dir / os.path.basename(u)).exists()]
    if todo:
        earthdata_login(credentials_ini)
        earthaccess.download(todo, str(dest_dir), show_progress=False)
    return [str(dest_dir / os.path.basename(u)) if u else None for u in urls]


# ============================================================ footprint-summarised reference surfaces

def read_on_grid(path, template, resampling=Resampling.bilinear):
    """Read a raster warped onto an open template dataset's grid (CRS, transform, shape); masked array."""
    from rasterio.vrt import WarpedVRT
    with rasterio.open(path) as src, WarpedVRT(src, crs=template.crs, transform=template.transform,
                                                width=template.width, height=template.height,
                                                resampling=resampling, src_nodata=src.nodata,
                                                nodata=np.nan) as vrt:
        a = vrt.read(1).astype("float32")
    return np.ma.masked_invalid(a)


def footprint_surfaces(chm_path, dtm_path, out_dir, footprint_m=11.0):
    """From 1 m G-LiHT (or resampled UAV) CHM and DTM, write two rasters on the CHM grid:
    '<stem>_dtmfp.tif'  mean DTM within the ICESat-2 footprint (circular, footprint_m diameter)
    '<stem>_topfp.tif'  DTM + maximum CHM within the footprint (absolute canopy-top height)
    Returns (dtmfp_path, topfp_path)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(chm_path).stem.replace("_CHM", "")
    dtm_out, top_out = out_dir / f"{stem}_dtmfp.tif", out_dir / f"{stem}_topfp.tif"
    if dtm_out.exists() and top_out.exists():
        return str(dtm_out), str(top_out)
    with rasterio.open(chm_path) as c:
        chm = c.read(1, masked=True).astype("float32")
        prof = c.profile
        res = c.res[0]
        dtm = read_on_grid(dtm_path, c)
    r = max(1, int(round(footprint_m / 2 / res)))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    fp = (xx ** 2 + yy ** 2) <= r ** 2
    chm_f = np.where(chm.mask, -9999, chm.filled(-9999))
    chm_max = ndimage.maximum_filter(chm_f, footprint=fp, mode="nearest")
    valid = (~dtm.mask).astype("float32")
    dsum = ndimage.convolve(np.where(dtm.mask, 0, dtm.filled(0)), fp.astype("float32"), mode="nearest")
    dcnt = ndimage.convolve(valid, fp.astype("float32"), mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        dmean = np.where(dcnt > 0.5 * fp.sum(), dsum / dcnt, np.nan).astype("float32")
    top = np.where((chm_max > -9999) & np.isfinite(dmean), dmean + np.maximum(chm_max, 0), np.nan).astype("float32")
    prof.update(driver="GTiff", dtype="float32", nodata=np.nan, count=1, compress="deflate", tiled=True,
                blockxsize=256, blockysize=256)
    prof.pop("photometric", None)
    for path, arr in ((dtm_out, dmean), (top_out, top)):
        with rasterio.open(path, "w", **prof) as o:
            o.write(arr, 1)
    return str(dtm_out), str(top_out)


def sample_raster(path, lon, lat, dx=0.0, dy=0.0):
    """Sample a single-band raster at lon/lat points (EPSG:4326), optionally shifted by dx, dy metres in
    the raster's projected CRS. NaN outside the raster or at nodata. Value of the pixel containing each point
    (as rasterio's sample()), read as one window covering the points instead of point by point."""
    lon, lat = np.asarray(lon), np.asarray(lat)
    with rasterio.open(path) as src:
        pts = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs="EPSG:4326").to_crs(src.crs)
        xs, ys = pts.x.to_numpy() + dx, pts.y.to_numpy() + dy
        return _sample_open(src, xs, ys)


def _sample_open(src, xs, ys, cache=None, block=1024):
    """Pixel values at projected points xs, ys (src CRS) from an open dataset; NaN outside or at nodata.
    Points are grouped into block x block pixel cells and each cell is read once as a small window, so a sparse track
    across a large mosaic does not read the whole raster. `cache` (dict) keeps the cells between calls (shift search)."""
    out = np.full(len(xs), np.nan, dtype="float64")
    inb = (xs >= src.bounds.left) & (xs < src.bounds.right) & (ys > src.bounds.bottom) & (ys <= src.bounds.top)
    if not inb.any():
        return out
    rows, cols = rowcol(src.transform, xs[inb], ys[inb], op=np.floor)
    rows, cols = np.asarray(rows, dtype=np.int64), np.asarray(cols, dtype=np.int64)
    vals = np.full(len(rows), np.nan)
    br, bc = rows // block, cols // block
    key = br * (src.width // block + 2) + bc
    for k in np.unique(key):
        m = key == k
        r0, c0 = int(br[m][0]) * block, int(bc[m][0]) * block
        ck = (src.name, r0, c0)
        arr = cache.get(ck) if cache is not None else None
        if arr is None:
            h, w = min(block, src.height - r0), min(block, src.width - c0)
            arr = src.read(1, window=Window(c0, r0, w, h)).astype("float32")
            if src.nodata is not None and np.isfinite(src.nodata):
                arr[arr == src.nodata] = np.nan
            if cache is not None:
                cache[ck] = arr
        vals[m] = arr[rows[m] - r0, cols[m] - c0]
    out[inb] = vals
    return out


class MosaicSampler:
    """sample_mosaic for many calls on the same points (e.g. a shift search): rasters opened once, points reprojected
    once per CRS, rasters that cannot reach the points (bounds + pad) skipped. Same values as sample_mosaic."""

    def __init__(self, paths, lon, lat, pad=0.0):
        self.srcs = [rasterio.open(p) for p in paths]
        pts = gpd.GeoSeries(gpd.points_from_xy(np.asarray(lon), np.asarray(lat)), crs="EPSG:4326")
        self.xy, keep = {}, []
        for src in self.srcs:
            k = src.crs.to_string()
            if k not in self.xy:
                q = pts.to_crs(src.crs)
                self.xy[k] = (q.x.to_numpy(), q.y.to_numpy())
            xs, ys = self.xy[k]
            b = src.bounds
            if (xs.max() + pad >= b.left) and (xs.min() - pad <= b.right) and (ys.max() + pad >= b.bottom) and (ys.min() - pad <= b.top):
                keep.append(src)
        self.use = keep
        self.n = len(pts)
        self.cache = {}                     # raster cells read so far (reused across shifts)

    def __call__(self, dx=0.0, dy=0.0):
        out = np.full(self.n, np.nan)
        for src in self.use:
            need = ~np.isfinite(out)
            if not need.any():
                break
            xs, ys = self.xy[src.crs.to_string()]
            out[need] = _sample_open(src, xs[need] + dx, ys[need] + dy, self.cache)
        return out

    def close(self):
        for s in self.srcs:
            s.close()


def sample_mosaic(paths, lon, lat, dx=0.0, dy=0.0):
    """First valid value across several rasters (overlapping strips)."""
    out = np.full(len(lon), np.nan)
    for p in paths:
        need = ~np.isfinite(out)
        if not need.any():
            break
        out[need] = sample_raster(p, np.asarray(lon)[need], np.asarray(lat)[need], dx, dy)
    return out


# ============================================================ geolocation / datum offset per track

def track_offsets(photons, dtm_paths, cfg, ground_mask=None):
    """Per track: horizontal shift (dx, dy in the raster CRS) and vertical offset dz that best align
    ground photons (ATL08 class 1 by default) with the reference DTM. dz absorbs datum differences
    (ellipsoid vs geoid) and is reported. Score = median absolute residual after removing the median."""
    rl = cfg["reference_labels"]
    shifts = np.arange(-rl["offset_search_m"], rl["offset_search_m"] + 1e-6, rl["offset_step_m"])
    rows = []
    gm = photons["atl08_class"].eq(1) if ground_mask is None else ground_mask
    for tid, g in photons[gm].groupby("track_id"):
        if len(g) < 20:
            continue
        g = g.sample(min(len(g), 3000), random_state=0)
        sampler = MosaicSampler(dtm_paths, g["lon"], g["lat"], pad=rl["offset_search_m"] + 1)
        best = None
        for dx in shifts:
            for dy in shifts:
                ref = sampler(dx, dy)
                res = g["height"].to_numpy() - ref
                res = res[np.isfinite(res)]
                if len(res) < 20:
                    continue
                med = np.median(res)
                score = np.median(np.abs(res - med))
                if best is None or score < best["mad"]:
                    best = {"track_id": tid, "dx": dx, "dy": dy, "dz": med, "mad": score, "n": len(res)}
        if best:
            gain = rl.get("offset_min_gain")
            if gain is not None and (best["dx"], best["dy"]) != (0.0, 0.0):
                # v0.2: keep a horizontal shift only if it clearly improves the ground fit over no shift
                ref0 = sampler(0.0, 0.0)
                res0 = g["height"].to_numpy() - ref0
                res0 = res0[np.isfinite(res0)]
                if len(res0) >= 20:
                    med0 = np.median(res0)
                    mad0 = np.median(np.abs(res0 - med0))
                    best["mad_noshift"] = mad0
                    if best["mad"] > (1 - gain) * mad0:
                        best.update({"dx": 0.0, "dy": 0.0, "dz": med0, "mad": mad0, "n": len(res0), "shift_rejected": True})
            rows.append(best)
        sampler.close()
    return pd.DataFrame(rows)


def label_photons(photons, dtmfp_paths, topfp_paths, offsets, cfg):
    """Reference labels for every photon, after applying the per-track offsets."""
    from icesat2_photon_lib import reference_label
    photons = photons.copy()
    photons["ref_ground"] = np.nan
    photons["ref_top"] = np.nan
    off = offsets.set_index("track_id")
    for tid, idx in photons.groupby("track_id").groups.items():
        if tid not in off.index:
            continue
        o = off.loc[tid]
        sub = photons.loc[idx]
        photons.loc[idx, "ref_ground"] = sample_mosaic(dtmfp_paths, sub["lon"], sub["lat"], o.dx, o.dy) + o.dz
        photons.loc[idx, "ref_top"] = sample_mosaic(topfp_paths, sub["lon"], sub["lat"], o.dx, o.dy) + o.dz
    photons["ref_label"] = reference_label(photons["height"], photons["ref_ground"], photons["ref_top"], cfg)
    photons["ref_relief"] = photons["height"] - photons["ref_ground"]
    return photons


# ============================================================ segment footprints and ALS metrics

def segment_footprints(segs, width_m=11.0, crs=None):
    """Rectangles along each 30 m segment (first to last photon), width_m across track.
    Built in a local UTM zone; returned in that CRS (or crs if given)."""
    utm = crs or gpd.GeoSeries(gpd.points_from_xy(segs["lon"], segs["lat"]), crs="EPSG:4326").estimate_utm_crs()
    p0 = gpd.GeoSeries(gpd.points_from_xy(segs["lon0"], segs["lat0"]), crs="EPSG:4326").to_crs(utm)
    p1 = gpd.GeoSeries(gpd.points_from_xy(segs["lon1"], segs["lat1"]), crs="EPSG:4326").to_crs(utm)
    geoms = [LineString([(a.x, a.y), (b.x, b.y)]).buffer(width_m / 2, cap_style=2) if a.distance(b) > 1
             else a.buffer(width_m / 2) for a, b in zip(p0, p1)]
    return gpd.GeoDataFrame(segs.drop(columns="geometry", errors="ignore"), geometry=geoms, crs=utm)


def als_segment_metrics(footprints, chm_paths, dx=0.0, dy=0.0, percentiles=(50, 75, 90, 95, 98, 100),
                        cover_thresholds=(0.5, 1.37, 2.0)):
    """CHM statistics inside each segment footprint, from the first CHM strip that covers it."""
    rows = []
    srcs = [rasterio.open(p) for p in chm_paths]
    try:
        for i, fp in footprints.iterrows():
            r = {"idx": i, "als_n": 0}
            for src in srcs:
                g = gpd.GeoSeries([fp.geometry], crs=footprints.crs).to_crs(src.crs).translate(dx, dy)
                if not g.iloc[0].intersects(box(*src.bounds)):
                    continue
                try:
                    arr, _ = rio_mask(src, [g.iloc[0]], crop=True, filled=False)
                except ValueError:
                    continue
                v = arr[0].compressed().astype(float)
                if src.nodata is not None:
                    v = v[v != src.nodata]
                if len(v) < 0.5 * fp.geometry.area:
                    continue
                v = np.clip(v, 0, None)
                r["als_n"] = len(v)
                for p in percentiles:
                    r[f"als_rh{p}"] = np.percentile(v, p)
                r["als_mean"] = v.mean()
                for t in cover_thresholds:
                    r[f"als_cover_{t:g}"] = float((v > t).mean())
                break
            rows.append(r)
    finally:
        for s in srcs:
            s.close()
    m = pd.DataFrame(rows).set_index("idx")
    return footprints.join(m)


# ============================================================ Seward Peninsula 2024

SEWARD_SITES = ["council_01", "council_02", "kougarok_01", "kougarok_02", "kougarok_03",
                "kougarok_04", "kougarok_05", "kougarok_06", "teller_01"]


def seward_inventory(seward_dir):
    """Per site: UAV footprint polygon (EPSG:4326), UAV DSM/DTM paths, earlier ATL03 extract (track used
    in the field) and number of field points."""
    seward_dir = Path(seward_dir)
    foot = gpd.read_file(seward_dir / "footprints_uav_sewardpen2024_RGB_COG.gpkg").to_crs(4326)
    field = gpd.read_file(seward_dir / "sew_pen_field_data_2024.gpkg").to_crs(4326)
    field["site_key"] = field["site"].str.lower()
    rows = []
    for s in SEWARD_SITES:
        f = foot[foot["site"].str.lower() == s]
        dsm = sorted((seward_dir / "DSM_COG").glob(f"{s}_*_dsm.tif"))
        dtm = sorted((seward_dir / "DTM_COG").glob(f"{s}_*_dtm.tif"))
        a03 = seward_dir / f"sewardpen2024_{s}_classified_photons_ATL03.gpkg"
        rows.append({"site": s, "geometry": f.geometry.union_all() if len(f) else None,
                     "dsm": str(dsm[0]) if dsm else None, "dtm": str(dtm[0]) if dtm else None,
                     "atl03_field_extract": str(a03) if a03.exists() else None,
                     "n_field_points": int((field["site_key"] == s).sum())})
    return gpd.GeoDataFrame(rows, crs="EPSG:4326"), field


def resample_to_1m(src_path, out_path, res=1.0, how=Resampling.max):
    """Resample a very fine UAV raster to 1 m (max for DSM/CHM, average for DTM) in its own CRS (warp)."""
    from rasterio.warp import reproject
    from rasterio.transform import from_origin
    out_path = Path(out_path)
    if out_path.exists():
        return str(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(src_path) as src:
        b = src.bounds
        w, h = max(1, int(np.ceil((b.right - b.left) / res))), max(1, int(np.ceil((b.top - b.bottom) / res)))
        transform = from_origin(b.left, b.top, res, res)
        dst = np.full((h, w), np.nan, dtype="float32")
        reproject(rasterio.band(src, 1), dst, src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                  dst_transform=transform, dst_crs=src.crs, dst_nodata=np.nan, resampling=how)
        prof = {"driver": "GTiff", "height": h, "width": w, "count": 1, "dtype": "float32", "crs": src.crs,
                "transform": transform, "nodata": np.nan, "compress": "deflate", "tiled": True,
                "blockxsize": 256, "blockysize": 256}
    with rasterio.open(out_path, "w", **prof) as o:
        o.write(dst, 1)
    return str(out_path)


def uav_chm(dsm_1m, dtm_1m, out_path):
    """CHM = DSM - DTM on the DSM grid (negative values set to 0)."""
    out_path = Path(out_path)
    if out_path.exists():
        return str(out_path)
    with rasterio.open(dsm_1m) as s:
        dsm = s.read(1)
        dtm = read_on_grid(dtm_1m, s).filled(np.nan)
        prof = s.profile
    chm = np.clip(dsm - dtm, 0, None).astype("float32")
    with rasterio.open(out_path, "w", **prof) as o:
        o.write(chm, 1)
    return str(out_path)


# ============================================================ disturbance screen

def hansen_lossyear(lon, lat, version="GFC-2024-v1.12"):
    """Hansen Global Forest Change loss year (0 = no loss, 1..24 = 2001..2024) at points, read from the
    public 10x10 degree tiles over HTTP."""
    lon, lat = np.asarray(lon), np.asarray(lat)
    out = np.zeros(len(lon), dtype="int16")
    tiles = {}
    for i, (x, y) in enumerate(zip(lon, lat)):
        ty = int(np.ceil(y / 10.0) * 10)
        tx = int(np.floor(x / 10.0) * 10)
        key = f"{abs(ty):02d}{'N' if ty >= 0 else 'S'}_{abs(tx):03d}{'E' if tx >= 0 else 'W'}"
        tiles.setdefault(key, []).append(i)
    for key, idx in tiles.items():
        url = f"/vsicurl/https://storage.googleapis.com/earthenginepartners-hansen/{version}/Hansen_{version}_lossyear_{key}.tif"
        try:
            with rasterio.open(url) as src:
                vals = np.array([v[0] for v in src.sample(zip(lon[idx], lat[idx]))])
            out[idx] = vals
        except Exception as err:
            print(f"Hansen tile {key}: {err}")
    return out
