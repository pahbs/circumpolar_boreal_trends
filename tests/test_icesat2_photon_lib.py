"""Synthetic-photon tests for each step of the reclassifier and the cover retrieval.
Run:  python -m pytest -q tests/"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import icesat2_photon_lib as ipl  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return ipl.load_config(profile="adapt")


@pytest.fixture(scope="module")
def cfg04():
    return ipl.load_config(Path(__file__).resolve().parents[1] / "config" / "atl03_reclass_v0.4.yaml", profile="adapt")


@pytest.fixture(scope="module")
def cfg05():
    return ipl.load_config(Path(__file__).resolve().parents[1] / "config" / "atl03_reclass_v0.5.yaml", profile="adapt")


@pytest.fixture(scope="module")
def cfg06():
    return ipl.load_config(Path(__file__).resolve().parents[1] / "config" / "atl03_reclass_v0.6.yaml", profile="adapt")


def synthetic_track(canopy_h=15.0, length=600.0, cover=0.6, bg_rate=2e5, slope=0.05, seed=0, footprint_m=0.0):
    """Photons over a sloping ground with a canopy of height canopy_h and given cover, plus background.
    footprint_m > 0 spreads ground returns over the footprint (+/- footprint_m / 2 x slope), as on real slopes."""
    rng = np.random.default_rng(seed)
    shots = np.arange(0, length, 0.7)
    xs, hs, cls = [], [], []
    for x in shots:
        g = 100 + slope * x
        for _ in range(rng.poisson(1.5)):
            if canopy_h > 0 and rng.random() < cover:
                xs.append(x); hs.append(g + rng.uniform(0.3 * canopy_h, canopy_h)); cls.append(2)
            else:
                xs.append(x); hs.append(g + rng.uniform(-0.5, 0.5) * footprint_m * slope + rng.normal(0, 0.15)); cls.append(1)
    # background photons in a 60 m window around ground
    n_bg = rng.poisson(bg_rate * (2 * 60 / ipl.C_LIGHT) * len(shots))
    xb = rng.uniform(0, length, n_bg)
    xs += list(xb); hs += list(100 + slope * xb + rng.uniform(-20, 40, n_bg)); cls += [0] * n_bg
    return np.array(xs), np.array(hs), np.array(cls), np.full(len(xs), bg_rate)


def test_expected_noise_scales_with_rate(cfg):
    a, b = ipl.expected_noise_count([1e5, 1e6], cfg)
    assert b == pytest.approx(10 * a)


def test_noise_filter_separates_signal(cfg):
    """Signal kept; background removed outside the ground-to-canopy envelope. Background photons inside the
    canopy volume are indistinguishable from canopy returns by density and are not counted here."""
    x, h, truth, br = synthetic_track(canopy_h=15.0)
    sig, _, _ = ipl.noise_filter(x, h, br, cfg)
    rel = h - (100 + 0.05 * x)
    outside = (truth == 0) & ((rel > 15.0 + 3.0) | (rel < -2.0))
    assert sig[truth > 0].mean() > 0.8          # most signal kept
    assert sig[outside].mean() < 0.05           # background away from the surfaces removed


def test_ground_surface_follows_slope(cfg):
    x, h, truth, br = synthetic_track(canopy_h=0.0)
    sig, _, _ = ipl.noise_filter(x, h, br, cfg)
    surf, _ = ipl.ground_surface(x, h, sig, cfg)
    g = truth == 1
    assert np.median(np.abs(surf[g] - (100 + 0.05 * x[g]))) < 0.3


def test_classify_track_recovers_canopy_height(cfg):
    x, h, truth, br = synthetic_track(canopy_h=20.0)
    cls, rel, _, _ = ipl.classify_track(x, h, br, cfg)
    rh98 = np.percentile(rel[np.isin(cls, (2, 3))], 98)
    assert abs(rh98 - 19.6) < 1.5
    gacc = (cls[truth == 1] == 1).mean()
    assert gacc > 0.8


def test_short_vegetation_not_inflated(cfg):
    """Bare ground with daytime background: segments must not report vegetation taller than 1 m."""
    x, h, truth, br = synthetic_track(canopy_h=0.0, bg_rate=3e6)
    df = pd.DataFrame({"x_atc": x, "height": h, "background_rate": br})
    df["track_id"] = "t"; df["rgt"] = 1; df["cycle"] = 1; df["gt"] = 10; df["spot"] = 1; df["strong"] = True
    df["lon"] = -150 + x * 1e-5; df["lat"] = 65.0; df["year"] = 2020; df["doy"] = 200; df["solar_elevation"] = 30
    out = ipl.reclassify(df, cfg)
    segs = ipl.segment_metrics(out, cfg)
    assert (segs["h_canopy"] > 1.0).mean() < 0.1


def _segments(x, h, br, cfg, solar_elevation=30):
    df = pd.DataFrame({"x_atc": x, "height": h, "background_rate": br})
    df["track_id"] = "t"; df["rgt"] = 1; df["cycle"] = 1; df["gt"] = 10; df["spot"] = 1; df["strong"] = True
    df["lon"] = -150 + x * 1e-5; df["lat"] = 65.0; df["year"] = 2020; df["doy"] = 200; df["solar_elevation"] = solar_elevation
    return ipl.segment_metrics(ipl.reclassify(df, cfg), cfg)


def test_v04_bare_slope_not_vegetation(cfg04):
    """v0.4: bare ground on a 20 degree slope (ground returns spread over the 11 m footprint) is not reported as
    vegetation; v0.3's fixed +/-0.6 m ground window called the upslope returns canopy."""
    x, h, truth, br = synthetic_track(canopy_h=0.0, slope=np.tan(np.radians(20)), footprint_m=11.0, bg_rate=5e5)
    segs = _segments(x, h, br, cfg04)
    assert (segs["h_canopy"] > 2.0).mean() < 0.1
    assert segs["ground_slope_deg"].median() == pytest.approx(20, abs=3)


def test_v04_sparse_forest_not_zero(cfg04):
    """v0.4: open tall canopy at the design cover (presence.min_cover = 25 %) under bright daytime background is
    (almost) never written as 0 m. v0.3 wrote 0 m for 20 % of these segments (< 5 canopy photons after background)."""
    x, h, truth, br = synthetic_track(canopy_h=18.0, cover=0.25, bg_rate=1e6)
    segs = _segments(x, h, br, cfg04)
    assert (segs["h_canopy"] == 0).mean() < 0.05


def test_v04_bare_flat_is_zero(cfg04):
    """v0.4: bare flat ground with enough ground signal gives 0 m (vegetation demonstrably absent), not NaN or a height."""
    x, h, truth, br = synthetic_track(canopy_h=0.0, slope=0.0, bg_rate=1e6)
    segs = _segments(x, h, br, cfg04)
    assert (segs["h_canopy"] == 0).mean() > 0.8


def _with_afterpulses(x, h, truth, br, depth=2.5, share=0.15, seed=3):
    """Add a cluster of photons `depth` m below every ground return with probability `share` (after-pulses under a
    bright, flat surface), labelled -1."""
    rng = np.random.default_rng(seed)
    g = np.flatnonzero(truth == 1)
    pick = g[rng.random(len(g)) < share]
    xa, ha = x[pick], h[pick] - depth + rng.normal(0, 0.2, len(pick))
    return np.r_[x, xa], np.r_[h, ha], np.r_[truth, np.full(len(pick), -1)], np.r_[br, br[pick]]


def test_v05_ground_not_pulled_down_by_afterpulses(cfg04, cfg05):
    """v0.5: photons 2.5 m below a bare flat surface (15 % of ground returns) do not pull the ground down. v0.4's
    lower envelope sat on them and called the true surface canopy (+2.5 m heights over bare ground)."""
    x, h, truth, br = _with_afterpulses(*synthetic_track(canopy_h=0.0, slope=0.0, bg_rate=2e5))
    cls, rel, _, _ = ipl.classify_track(x, h, br, cfg05)
    assert np.median(np.abs(rel[truth == 1])) < 0.2              # surface photons sit on the v0.5 ground
    assert (cls[truth == 1] == 1).mean() > 0.9
    s04, s05 = _segments(x, h, br, cfg04), _segments(x, h, br, cfg05)
    assert (s05["h_canopy"] > 1.0).mean() < 0.1
    assert (s04["h_canopy"] > 1.0).mean() > (s05["h_canopy"] > 1.0).mean()


def test_v05_forest_height_kept(cfg05):
    """v0.5: under a 15 m canopy at 60 % cover the ground is still the lowest dense layer, not a canopy layer."""
    x, h, truth, br = synthetic_track(canopy_h=15.0, cover=0.6, slope=0.05)
    segs = _segments(x, h, br, cfg05)
    assert segs["h_canopy"].median() == pytest.approx(15.0, abs=1.5)


def test_reference_label_windows(cfg):
    lab = ipl.reference_label([100.0, 105.0, 120.0, 140.0, 90.0], [100.0] * 5, [118.0] * 5, cfg)
    assert list(lab) == ["ground", "canopy", "buffer", "noise", "noise"]


def test_reflectance_ratio_recovered(cfg):
    """Ev = cv*rv*E, Eg = (1-cv)*rg*E with varying E per track -> fitted ratio ~ rv/rg."""
    rng = np.random.default_rng(1)
    rows = []
    for t in range(6):
        E = rng.uniform(1.5, 3.0)
        for cv in rng.uniform(0, 1, 60):
            rows.append({"track_id": t, "Ev": cv * 0.8 * E + rng.normal(0, 0.03),
                         "Eg": (1 - cv) * 1.0 * E + rng.normal(0, 0.03)})
    fit = ipl.fit_reflectance_ratio(pd.DataFrame(rows), cfg)
    assert fit["ratio"] == pytest.approx(0.8, abs=0.05)


def test_canopy_cover_formula():
    assert ipl.canopy_cover(10, 10, 1.0) == pytest.approx(0.5)
    assert ipl.canopy_cover(10, 10, 0.5) == pytest.approx(1 / 1.5)
    assert ipl.canopy_cover(0, 10, 1.0) == 0.0


def test_confusion_pairs_photons_by_position():
    """Regression test: reference labels with a non-default index must pair with classes by position."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    import validation_lib as val
    ref = pd.Series(["ground", "canopy", "canopy"], index=[10, 11, 12])
    est = pd.Series([1, 2, 2], index=[10, 11, 12])
    t, tn = val.confusion(ref, est, {1: "ground", 2: "canopy"})
    assert t.loc["ground", "ground"] == 1 and t.loc["canopy", "canopy"] == 2


def test_v06_sparse_ground_under_dense_canopy(cfg05, cfg06):
    """v0.6: under 85 % canopy cover (~3 ground photons per 10 m bin) the ground stays on the ground photons; v0.5's
    3-photon minimum lost it in bins with fewer. Known limit: with <= ~2 ground photons per bin (90 % cover here) every
    density-based start, v0.5 and v0.6 alike, starts on a canopy layer, where v0.4's lower envelope does better."""
    x, h, truth, br = synthetic_track(canopy_h=20.0, cover=0.85, slope=0.0, bg_rate=2e4, seed=0)
    e05 = np.median(np.abs(ipl.classify_track(x, h, br, cfg05)[1][truth == 1]))
    e06 = np.median(np.abs(ipl.classify_track(x, h, br, cfg06)[1][truth == 1]))
    assert e06 < 0.2 and e06 < e05


def test_v06_keeps_v05_afterpulse_fix(cfg06):
    x, h, truth, br = _with_afterpulses(*synthetic_track(canopy_h=0.0, slope=0.0, bg_rate=2e5))
    cls, rel, _, _ = ipl.classify_track(x, h, br, cfg06)
    assert np.median(np.abs(rel[truth == 1])) < 0.2
