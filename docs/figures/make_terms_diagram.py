"""Terms diagram for the summary deck and notebooks (docs/figures/terms_diagram.png). Names as of 17 Oct 2026:
a 30 m version is named by whose photon classes, then who binned them into 30 m segments.
Run:  python docs/figures/make_terms_diagram.py"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

INK, INK2 = "#0b0b0b", "#52514e"
FILL = {"photons": "#eeeeec", "atl08": "#e6e5e0", "ours": "#dbe8f8", "ref": "#f6e7d3"}
EDGE = {"photons": "#898781", "atl08": "#898781", "ours": "#184f95", "ref": "#a8784a"}


def box(ax, x, y, w, h, title, text, kind, bold_edge=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.12", fc=FILL[kind],
                                ec=EDGE[kind], lw=2.0 if bold_edge else 1.0))
    ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=12, fontweight="bold", color=INK)
    ax.text(x + w / 2, y + h * 0.30, text, ha="center", va="center", fontsize=9.5, color=INK2, linespacing=1.3)


def arrow(ax, x0, y0, x1, y1):
    ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.1, shrinkA=0, shrinkB=0))


fig, ax = plt.subplots(figsize=(14, 6.9))
ax.set_xlim(0, 14); ax.set_ylim(0, 6.9); ax.axis("off")
ax.text(0.1, 6.8, "A 30 m height is made in two steps: label the photons, then bin them into 30 m segments",
        fontsize=14, fontweight="bold", color=INK, va="top")
ax.text(0.1, 6.35, "Each version name says both: whose photon labels · who did the binning. All use ICESat-2 data release 007 (\"v7\").",
        fontsize=10, color=INK2, va="top")
for x, t in [(3.6, "Step 1 · label each photon"), (8.1, "Step 2 · bin into 30 m segments, compute height (RH98)")]:
    ax.text(x, 5.78, t, fontsize=10, color=INK2, fontweight="bold", va="center")

box(ax, 0.05, 2.55, 3.1, 1.3, "ATL03 photons", "every photon ICESat-2 recorded\n(signal + sunlight noise)", "photons")
box(ax, 3.6, 4.0, 3.6, 1.25, "ATL08 photon classes", "NASA's ground / canopy / noise\nlabels (used today)", "atl08")
box(ax, 3.6, 2.35, 3.6, 1.25, "Reclassified photon classes", "our labels for the same photons\n(config v0.1 … v0.4)", "ours")
box(ax, 3.6, 0.35, 3.6, 1.25, "Reference photon labels", "the truth, from airborne lidar\nor drone surface models", "ref")
box(ax, 8.1, 4.55, 5.8, 0.95, "ATL08 · PhoREAL (today)", "NASA labels, PhoREAL binning: our training data today", "atl08")
box(ax, 8.1, 3.45, 5.8, 0.95, "ATL08 · our binning (control)", "same NASA labels, our binning: what binning alone changes", "atl08")
box(ax, 8.1, 2.35, 5.8, 0.95, "Reclassified v0.N", "our labels, our binning: the candidate (v0.4 = latest)", "ours", bold_edge=True)
box(ax, 8.1, 0.35, 5.8, 1.25, "Reference height", "98th percentile of the lidar / drone canopy height\ninside each 30 m × 11 m footprint", "ref")
ax.text(11.0, 1.95, "▲ every version is compared with this ▲", ha="center", fontsize=9.5, color="#7a5530")

arrow(ax, 3.15, 3.35, 3.6, 4.55); arrow(ax, 3.15, 3.2, 3.6, 2.97); arrow(ax, 3.15, 3.05, 3.6, 1.0)
arrow(ax, 7.2, 4.75, 8.1, 5.0); arrow(ax, 7.2, 4.5, 8.1, 3.9); arrow(ax, 7.2, 2.97, 8.1, 2.82); arrow(ax, 7.2, 0.97, 8.1, 0.97)
out = Path(__file__).with_name("terms_diagram.png")
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
print("wrote", out)
