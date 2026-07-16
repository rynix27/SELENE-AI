"""
data_simulator.py
==================
Stands in for real Chandrayaan-2 DFSAR + OHRC products (ISSDC PRADAN access).

Generates a synthetic raster grid representing a 'doubly shadowed crater' in
the lunar south polar region, with physically-plausible spatial structure for:
  - CPR        (Circular Polarization Ratio)
  - DOP        (Degree of Polarization)
  - m-chi decomposition components (surface / volume / double-bounce power)
  - slope (degrees)
  - roughness (unitless RMS proxy)
  - solar illumination (hours/day)

The crater floor (permanently shadowed, cold-trap candidate) is seeded with
elevated volume-scattering / CPR to represent a plausible ice-bearing target,
while the rim and surrounding rough ejecta blanket produce CPR-confusable
signatures purely from double-bounce roughness scattering -- this is the
"false positive" problem SELENE-AI's m-chi fusion is designed to resolve.

This module is clearly a stand-in for real data. Swap `load_real_dfsar()`
in for `simulate_crater_scene()` once ISSDC-downloaded DFSAR/OHRC rasters
are available; the rest of the pipeline is agnostic to the data source as
long as the same field names are produced.
"""

import numpy as np

GRID_SIZE = 80          # 80x80 pixel scene (e.g. ~20m/px -> 1.6km x 1.6km)
PIXEL_SIZE_M = 20.0
RNG_SEED = 42


def _radial_grid(n):
    y, x = np.mgrid[0:n, 0:n]
    cx, cy = n / 2, n / 2
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / (n / 2)
    return r, x, y


def simulate_crater_scene(n=GRID_SIZE, seed=RNG_SEED):
    """Generate a synthetic doubly-shadowed crater scene.

    Returns a dict of 2D numpy arrays, one per physical field, plus metadata.
    """
    rng = np.random.default_rng(seed)
    r, x, y = _radial_grid(n)

    # --- Topography: crater bowl with raised rim ---------------------------
    crater_radius = 0.55
    depth = np.clip(1 - (r / crater_radius) ** 2, -0.3, 1) * 40      # meters
    rim_bump = 8 * np.exp(-((r - crater_radius) ** 2) / (2 * 0.03 ** 2))
    elevation = -depth + rim_bump + rng.normal(0, 1.2, size=(n, n))

    # slope (deg) from elevation gradient
    gy, gx = np.gradient(elevation, PIXEL_SIZE_M)
    slope = np.degrees(np.arctan(np.sqrt(gx ** 2 + gy ** 2)))
    slope = np.clip(slope + rng.normal(0, 1.0, size=(n, n)), 0, 45)   # +/-3deg noise as per doc

    # roughness: high on rim/ejecta, lower on smooth floor, patchy boulders
    roughness = (
        0.3
        + 0.5 * np.exp(-((r - crater_radius) ** 2) / (2 * 0.05 ** 2))   # rim/ejecta rough
        + 0.15 * (r > crater_radius)                                     # ejecta blanket
        + rng.normal(0, 0.05, size=(n, n))
    )
    roughness = np.clip(roughness, 0.05, 1.0)

    # --- Illumination: floor is permanently shadowed (the PSR) -------------
    floor_mask = r < crater_radius * 0.55
    illumination_hours = np.where(
        floor_mask,
        rng.uniform(0.0, 0.3, size=(n, n)),          # near-zero: PSR floor
        np.clip(8 * (1 - r) + rng.normal(0, 1.0, size=(n, n)), 0, 14),
    )

    # --- Radar scattering mechanisms (m-chi style powers) -------------------
    # Volume scattering: elevated within a sub-region of the shadowed floor
    # (the plausible ice patch) -> the ground-truth-like seed for validation.
    true_ice_cx, true_ice_cy = n * 0.47, n * 0.5
    ice_seed_r = np.sqrt((x - true_ice_cx) ** 2 + (y - true_ice_cy) ** 2) / (n * 0.16)
    ice_patch = np.clip(1 - ice_seed_r, 0, 1) ** 1.5
    ice_patch *= floor_mask

    volume_power = 0.15 + 0.65 * ice_patch + rng.normal(0, 0.04, size=(n, n))
    volume_power = np.clip(volume_power, 0.01, 1.0)

    # Double-bounce scattering: dominant on rough rim/ejecta (rock fields),
    # this is what confuses CPR-only detectors into false positives.
    double_bounce_power = np.clip(
        0.1 + 0.7 * np.exp(-((r - crater_radius) ** 2) / (2 * 0.05 ** 2))
        + rng.normal(0, 0.05, size=(n, n)),
        0.01, 1.0,
    )

    surface_power = np.clip(1.0 - volume_power - double_bounce_power, 0.05, 1.0)
    total = surface_power + volume_power + double_bounce_power
    surface_power, volume_power, double_bounce_power = (
        surface_power / total, volume_power / total, double_bounce_power / total,
    )

    # CPR: driven mainly by volume scattering (ice), inflated somewhat by
    # double-bounce (the classic confusable case) -- this is intentional so
    # that CPR-only thresholding produces false positives on the rim.
    cpr = (
        0.55
        + 1.1 * volume_power
        + 0.65 * double_bounce_power          # <-- source of false positives
        + rng.normal(0, 0.05, size=(n, n))
    )
    cpr = np.clip(cpr, 0.2, 2.2)

    # DOP: high for coherent surface/double-bounce scattering, LOW for
    # volume (depolarizing) scattering -> genuine ice separator.
    dop = np.clip(
        0.85 - 0.75 * volume_power + rng.normal(0, 0.04, size=(n, n)), 0.02, 0.98
    )

    return {
        "elevation_m": elevation,
        "slope_deg": slope,
        "roughness": roughness,
        "illumination_hours": illumination_hours,
        "cpr": cpr,
        "dop": dop,
        "surface_power": surface_power,
        "volume_power": volume_power,
        "double_bounce_power": double_bounce_power,
        "floor_mask": floor_mask.astype(float),
        "_true_ice_patch": ice_patch,   # kept private: used only for validation scoring
        "meta": {
            "pixel_size_m": PIXEL_SIZE_M,
            "grid_size": n,
            "crater_name": "Simulated PSR crater (Faustini-type doubly shadowed crater)",
            "source": "SYNTHETIC -- stand-in for Chandrayaan-2 DFSAR + OHRC (ISSDC PRADAN)",
        },
    }


if __name__ == "__main__":
    scene = simulate_crater_scene()
    for k, v in scene.items():
        if isinstance(v, np.ndarray):
            print(f"{k:22s} shape={v.shape} min={v.min():.3f} max={v.max():.3f}")
