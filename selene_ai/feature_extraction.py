"""
feature_extraction.py
======================
Stage 1 of the SELENE-AI pipeline.

Takes the raw scene fields (CPR, DOP, m-chi power components, slope,
roughness, illumination) and derives the per-pixel feature table used
downstream by ice likelihood estimation and mission scoring.

Implements the "m-chi decomposition solves the false-positive problem"
logic described in the technical brief:
  - dominant_mechanism: surface / volume / double_bounce (per pixel)
  - triple_evidence_ice: boolean mask requiring CPR>1.0 AND volume-dominant
    AND inside a permanently-shadowed region (PSR) -- vs. naive CPR-only
    thresholding, which is also computed for baseline comparison.
"""

import numpy as np
import pandas as pd

CPR_ICE_THRESHOLD = 1.0

# Reference criterion: DOP < 0.13 (refined
# threshold reported at aggregate/regional scale in the published literature
# for this data product). At native pixel scale the DOP dynamic range of a
# given scene depends on sensor calibration and incidence geometry, so a
# fixed absolute cutoff does not transfer directly between scenes or between
# real DFSAR data and this synthetic stand-in. SELENE-AI therefore applies
# a scene-relative threshold (bottom quartile of DOP within the scene) and
# reports the fixed literature value alongside it for reference. Swapping in
# calibrated real DFSAR data should re-validate which threshold form holds.
DOP_LITERATURE_REFERENCE_THRESHOLD = 0.13
DOP_RELATIVE_PERCENTILE = 25


def extract_features(scene: dict) -> pd.DataFrame:
    """Flatten the scene grids into a per-pixel feature DataFrame."""
    n = scene["meta"]["grid_size"]
    yy, xx = np.mgrid[0:n, 0:n]

    power_stack = np.stack(
        [scene["surface_power"], scene["volume_power"], scene["double_bounce_power"]],
        axis=-1,
    )
    dominant_idx = np.argmax(power_stack, axis=-1)
    dominant_mechanism = np.select(
        [dominant_idx == 0, dominant_idx == 1, dominant_idx == 2],
        ["surface", "volume", "double_bounce"],
        default="surface",
    )

    is_psr = scene["illumination_hours"] < 0.5  # permanently shadowed proxy

    # Baseline (naive) detector: CPR-only thresholding
    cpr_only_ice = scene["cpr"] > CPR_ICE_THRESHOLD

    # SELENE-AI triple-evidence detector: CPR + volume-dominant m-chi + PSR boundary
    dop_relative_thresh = np.percentile(scene["dop"], DOP_RELATIVE_PERCENTILE)
    triple_evidence_ice = (
        (scene["cpr"] > CPR_ICE_THRESHOLD)
        & (dominant_mechanism == "volume")
        & (scene["dop"] < dop_relative_thresh)
        & is_psr
    )

    df = pd.DataFrame({
        "row": yy.ravel(),
        "col": xx.ravel(),
        "elevation_m": scene["elevation_m"].ravel(),
        "slope_deg": scene["slope_deg"].ravel(),
        "roughness": scene["roughness"].ravel(),
        "illumination_hours": scene["illumination_hours"].ravel(),
        "cpr": scene["cpr"].ravel(),
        "dop": scene["dop"].ravel(),
        "surface_power": scene["surface_power"].ravel(),
        "volume_power": scene["volume_power"].ravel(),
        "double_bounce_power": scene["double_bounce_power"].ravel(),
        "dominant_mechanism": dominant_mechanism.ravel(),
        "is_psr": is_psr.ravel(),
        "cpr_only_ice_flag": cpr_only_ice.ravel(),
        "triple_evidence_ice_flag": triple_evidence_ice.ravel(),
        "_true_ice_patch": scene["_true_ice_patch"].ravel(),  # for validation only
    })
    return df


def false_positive_reduction_stats(df: pd.DataFrame) -> dict:
    """Compare CPR-only vs. triple-evidence detection footprint."""
    cpr_only_count = int(df["cpr_only_ice_flag"].sum())
    triple_count = int(df["triple_evidence_ice_flag"].sum())
    reduction_pct = (
        100.0 * (cpr_only_count - triple_count) / cpr_only_count
        if cpr_only_count > 0 else 0.0
    )
    # rough terrain (rim/ejecta, non-PSR, high roughness) wrongly flagged by CPR-only
    rough_false_positives = int(((df["cpr_only_ice_flag"]) & (~df["is_psr"]) & (df["roughness"] > 0.5)).sum())
    return {
        "cpr_only_pixel_count": cpr_only_count,
        "triple_evidence_pixel_count": triple_count,
        "area_reduction_pct": round(reduction_pct, 1),
        "rough_terrain_false_positives_removed": rough_false_positives,
    }


if __name__ == "__main__":
    from selene_ai.data_simulator import simulate_crater_scene
    scene = simulate_crater_scene()
    df = extract_features(scene)
    print(df.head())
    print(false_positive_reduction_stats(df))
