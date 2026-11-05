"""Sanity check (LOG 19 Oct 2026): rule (a) of v0.7, night RH100, applied to the control (ATL08 photon classes, our binning).

Build (heavy; run on a forest node): rebuild the control 30 m segments from the saved photons exactly as
validation_lib.segments_all_versions does, keep the highest canopy photon (h_max_canopy) and apply the v0.7 night test
(expected background in the canopy window < segments.night_top.max_background_photons). Output, per reference:
runs/v0.7/variants/control_night_top_<ref>.parquet with keys + h_canopy_ctl98 (recomputed control, must equal the stored
h_canopy_atl08) and h_canopy_ctl100.
    python v07_control_night_top.py build [n_workers]
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))
import geopandas as gpd
import icesat2_photon_lib as ipl

cfg = ipl.load_config(REPO / "config" / "atl03_reclass_v0.7.yaml")
WORK = Path(cfg["paths"]["work_dir"]); RUN = WORK / "runs" / "v0.7"; OUT = RUN / "variants"
C_LIGHT = 299792458.0


def control_segments(photon_file):
    ph = gpd.read_parquet(photon_file)
    nat = ipl.segment_metrics(ipl.native_relief(ph, cfg), cfg, "atl08_class", "relief_atl08", "atl08")
    if not len(nat):
        return pd.DataFrame()
    mu = nat.background_rate * 2.0 / C_LIGHT * nat.n_shots * nat.h_max_canopy.fillna(0.0)
    use = (nat.h_canopy > 0) & (mu < cfg["segments"]["night_top"]["max_background_photons"]) & nat.h_max_canopy.notna()
    return pd.DataFrame({"track_id": nat.track_id, "seg": nat.seg, "h_canopy_ctl98": nat.h_canopy,
                         "h_canopy_ctl100": nat.h_canopy.where(~use, nat.h_max_canopy), "ctl_night_top": use,
                         "n_canopy_ctl": nat.n_canopy,
                         "file": Path(photon_file).parent.name if Path(photon_file).stem == "photons" else Path(photon_file).stem})


def build(workers):
    sources = {"glihit": sorted((RUN / "glihit").glob("tile_*/photons.parquet")),
               "seward": sorted((RUN / "seward").glob("*_photons.parquet")),
               "canelevation": [f for f in sorted((WORK / "canelevation" / "photons").glob("*.parquet")) if not f.stem.endswith("_phoreal")],
               "lvis": [f for f in sorted((WORK / "lvis" / "photons").glob("*.parquet")) if not f.stem.endswith("_phoreal")]}
    with ProcessPoolExecutor(workers) as ex:
        for ref, files in sources.items():
            parts = list(ex.map(control_segments, files))
            d = pd.concat([p for p in parts if len(p)], ignore_index=True)
            d.to_parquet(OUT / f"control_night_top_{ref}.parquet", index=False)
            print(ref, len(files), "files", len(d), "segments", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(int(sys.argv[2]) if len(sys.argv) > 2 else 8)
