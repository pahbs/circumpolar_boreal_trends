"""Shared figure style for the ATL03 reclassification notebooks: vegetation-height colormap and basemaps.

Vegetation height colormap: the one used for the VHR / ICESat-2 height layers in
https://pahbs.github.io/maap_tools/maps/Review_maps_v3.1_height_VHR.html (gray at 0 m, through browns, oranges and
yellows, to dark green at ~8.5 m; scale 0-10 m). Reproduced exactly from that page's 500 colour samples.
Heights above vmax take the top colour (dark green); use extend="max" on colorbars.

Maps: ESRI World Light Gray Canvas basemap (contextily provider Esri.WorldGrayCanvas) behind every map.
"""

from __future__ import annotations

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, Normalize

# (first sample index, colour) runs over 500 samples spanning 0-10 m
_HEIGHT_RUNS = [
    (0, "#636363"), (8, "#656463"), (9, "#726862"), (10, "#7c6c62"), (16, "#816e62"), (17, "#8e7262"), (18, "#967562"),
    (24, "#9d7762"), (25, "#aa7c61"), (26, "#b07e61"), (34, "#ba8161"), (35, "#c68661"), (36, "#c98761"), (42, "#d58b60"),
    (43, "#e39060"), (49, "#e49060"), (50, "#f29560"), (51, "#fd9960"), (61, "#fd9b62"), (62, "#fda267"), (63, "#fda66a"),
    (75, "#fdab6d"), (76, "#fdb272"), (77, "#fdb474"), (87, "#fdba79"), (88, "#fdc17e"), (98, "#fdc27f"), (99, "#fdca84"),
    (100, "#fdcf88"), (112, "#fdd28a"), (113, "#fdd990"), (114, "#fddc92"), (124, "#fde296"), (125, "#fde99b"),
    (126, "#fdea9c"), (138, "#fceb9d"), (139, "#faec9d"), (149, "#faed9d"), (150, "#f9ee9e"), (151, "#f7ee9e"),
    (161, "#f7ef9f"), (162, "#f5f0a0"), (163, "#f4f0a0"), (175, "#f3f1a1"), (176, "#f2f2a1"), (177, "#f1f2a1"),
    (186, "#f1f3a1"), (187, "#f0f4a2"), (188, "#eef4a2"), (198, "#eef5a3"), (199, "#ecf6a4"), (200, "#ebf6a4"),
    (212, "#e7f5a1"), (213, "#e1f29c"), (214, "#dff19a"), (224, "#daef96"), (225, "#d5ed91"), (226, "#d4ec91"),
    (237, "#d3ec90"), (238, "#cde98b"), (239, "#c9e788"), (249, "#c6e686"), (250, "#c0e481"), (251, "#bde27f"),
    (261, "#b9e07c"), (262, "#b3de77"), (263, "#b2dd76"), (275, "#acdb71"), (276, "#a7d96d"), (286, "#a4d86c"),
    (287, "#99d36a"), (288, "#92cf68"), (298, "#8ccd67"), (299, "#81c865"), (300, "#7dc664"), (312, "#74c262"),
    (313, "#6abe5f"), (314, "#69bd5f"), (323, "#68bd5f"), (324, "#5db85d"), (325, "#54b35b"), (337, "#4fb15a"),
    (338, "#45ad57"), (339, "#3faa56"), (349, "#38a754"), (350, "#2ea252"), (351, "#2ba152"), (361, "#279b4f"),
    (362, "#23954c"), (374, "#22944b"), (375, "#1e8d49"), (376, "#1c8947"), (386, "#1a8646"), (387, "#168043"),
    (388, "#157d42"), (398, "#12783f"), (399, "#0e723c"), (400, "#0e713c"), (411, "#0d713c"), (412, "#0a6a39"),
    (413, "#076537"), (423, "#056336"), (424, "#025d33"), (425, "#005a32"),
]
HEIGHT_VMIN, HEIGHT_VMAX = 0.0, 10.0
HEIGHT_LABEL = "Vegetation height (m)"


def _expand(runs, n=500):
    starts = [k for k, _ in runs] + [n]
    return [c for (k, c), k1 in zip(runs, starts[1:]) for _ in range(k1 - k)]


HEIGHT_CMAP = ListedColormap(_expand(_HEIGHT_RUNS), name="veg_height_vhr")
HEIGHT_CMAP.set_over("#005a32")
HEIGHT_CMAP.set_bad((0, 0, 0, 0))
mpl.colormaps.register(HEIGHT_CMAP, force=True)


def height_norm(vmin=HEIGHT_VMIN, vmax=HEIGHT_VMAX):
    return Normalize(vmin=vmin, vmax=vmax)


def height_colorbar(mappable, ax, label=HEIGHT_LABEL, **kw):
    """Colorbar for vegetation height; heights above the scale show as the top colour (extend arrow)."""
    kw.setdefault("extend", "max")
    kw.setdefault("shrink", 0.8)
    cb = plt.colorbar(mappable, ax=ax, **kw)
    cb.set_label(label)
    return cb


# ------------------------------------------------------------------ basemap

BASEMAP_ATTRIBUTION = "Basemap: Esri, HERE, Garmin, OpenStreetMap contributors"


def add_basemap(ax, crs, zoom="auto", alpha=1.0, attribution=True):
    """ESRI World Light Gray Canvas under the data already drawn on ax (ax in the given CRS).
    Needs internet access to server.arcgisonline.com; on failure the map is left without a basemap and a note is printed."""
    try:
        import contextily as cx
        cx.add_basemap(ax, crs=crs, source=cx.providers.Esri.WorldGrayCanvas, zoom=zoom, alpha=alpha,
                       attribution=BASEMAP_ATTRIBUTION if attribution else False, attribution_size=6, zorder=0)
    except Exception as e:  # offline node, tile server down
        print(f"basemap not added ({type(e).__name__}: {e})")
    return ax


def map_axes(ax, title=None):
    """Clean map frame: no ticks, equal aspect, light frame."""
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlabel(""); ax.set_ylabel("")
    ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_color("0.7"); s.set_linewidth(0.6)
    if title:
        ax.set_title(title, loc="left")
    return ax


def plot_height_points(ax, gdf, col="h_canopy", crs=3857, markersize=3, vmax=HEIGHT_VMAX, colorbar=True, basemap=True):
    """Segments (or photons) coloured by vegetation height on the light-gray basemap. Drawn in `crs` (Web Mercator by
    default, so basemap tiles are not warped); NaN heights are drawn as small light-gray points so data gaps stay visible."""
    g = gdf.to_crs(crs)
    nan = g[col].isna()
    if nan.any():
        g[nan].plot(ax=ax, color="0.85", markersize=markersize * 0.4, zorder=2)
    sc = ax.scatter(g[~nan].geometry.x, g[~nan].geometry.y, c=g.loc[~nan, col], s=markersize, lw=0,
                    cmap=HEIGHT_CMAP, norm=height_norm(vmax=vmax), zorder=3)
    if basemap:
        add_basemap(ax, crs)
    map_axes(ax)
    if colorbar:
        height_colorbar(sc, ax)
    return sc


# ------------------------------------------------------------------ general look

STYLE = {
    "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight", "figure.facecolor": "white",
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelsize": 10, "axes.labelcolor": "0.2", "xtick.labelsize": 9, "ytick.labelsize": 9,
    "xtick.color": "0.3", "ytick.color": "0.3", "axes.edgecolor": "0.6", "axes.linewidth": 0.7,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "0.92", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "legend.fontsize": 8, "legend.frameon": False,
}


def apply():
    """Use at the top of every notebook: plt.rcParams.update(...) with the shared style."""
    plt.rcParams.update(STYLE)
