"""
mission_scoring.py
====================
Stages 3-4 of the SELENE-AI pipeline: Mission Suitability Scoring & Ranking.

Generates candidate landing sites (safe, illuminated patches near the PSR
boundary), scores each against three configurable mission profiles
(Science-First / Safety-First / Balanced), and produces an explainable,
ranked shortlist with trade-off annotations.
"""

import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter, label

# Mission profile weights (must sum to 1.0 each), taken from the technical brief
PROFILES = {
    "science_first": {"ice": 0.50, "slope": 0.15, "solar": 0.10, "roughness": 0.10, "distance": 0.15},
    "safety_first":  {"ice": 0.15, "slope": 0.35, "solar": 0.30, "roughness": 0.15, "distance": 0.05},
    "balanced":      {"ice": 0.35, "slope": 0.25, "solar": 0.20, "roughness": 0.10, "distance": 0.10},
}

SLOPE_HARD_LIMIT_DEG = 20.0
MIN_SOLAR_HOURS = 4.0
CANDIDATE_PATCH_RADIUS_PX = 3    # ~60m radius window for local slope/roughness/solar averaging
ICE_PROXIMITY_RADIUS_PX = 10     # wider window: "ice richness of the surrounding target zone"
                                  # (landing sites sit just outside the PSR, so a site's own
                                  # ice_likelihood is ~0 by construction; what matters for
                                  # ranking is how rich the *adjacent* PSR target zone is)


def _local_average(grid, radius):
    size = radius * 2 + 1
    return uniform_filter(grid, size=size, mode="nearest")


def generate_candidate_sites(scene: dict, df_ice: pd.DataFrame, n_candidates: int = 6) -> pd.DataFrame:
    """Scan the scene for locally-safe, illuminated candidate landing patches
    near (but not inside) the permanently shadowed floor, then rank by a
    simple multi-factor local score to shortlist n_candidates diverse sites.
    """
    n = scene["meta"]["grid_size"]
    ice_grid = df_ice["ice_likelihood_pct"].values.reshape(n, n) / 100.0

    slope_avg = _local_average(scene["slope_deg"], CANDIDATE_PATCH_RADIUS_PX)
    rough_avg = _local_average(scene["roughness"], CANDIDATE_PATCH_RADIUS_PX)
    solar_avg = _local_average(scene["illumination_hours"], CANDIDATE_PATCH_RADIUS_PX)
    # Ice score uses a wider window: a landing site's own patch has near-zero
    # ice by construction (it must be outside the PSR to be safe/illuminated);
    # what differentiates sites is how close/rich the adjacent PSR ice zone is.
    ice_avg = _local_average(ice_grid, ICE_PROXIMITY_RADIUS_PX)

    floor_mask = scene["floor_mask"].astype(bool)
    # distance in pixels to nearest high-ice-likelihood pixel (Stage-1/2 target)
    ice_targets = np.argwhere(ice_grid > np.percentile(ice_grid, 97))
    yy, xx = np.mgrid[0:n, 0:n]
    if len(ice_targets) > 0:
        dists = np.min(
            [np.sqrt((yy - ty) ** 2 + (xx - tx) ** 2) for ty, tx in ice_targets], axis=0
        )
    else:
        dists = np.full((n, n), n)

    # Safe-landing eligibility mask: hard constraints
    eligible = (slope_avg <= SLOPE_HARD_LIMIT_DEG) & (solar_avg >= MIN_SOLAR_HOURS) & (~floor_mask)

    # crude scan: pick well-separated local maxima of a quick composite score
    composite = (
        0.4 * ice_avg
        + 0.3 * (1 - slope_avg / 45.0)
        + 0.2 * (solar_avg / 14.0)
        + 0.1 * (1 - rough_avg)
    )
    composite = np.where(eligible, composite, -1)

    candidates = []
    used_mask = np.zeros_like(composite, dtype=bool)
    flat_order = np.argsort(composite, axis=None)[::-1]
    min_sep = max(4, n // 12)
    for idx in flat_order:
        if len(candidates) >= n_candidates:
            break
        ry, cx = np.unravel_index(idx, composite.shape)
        if composite[ry, cx] <= 0:
            break
        if used_mask[ry, cx]:
            continue
        candidates.append((ry, cx))
        y0, y1 = max(0, ry - min_sep), min(n, ry + min_sep)
        x0, x1 = max(0, cx - min_sep), min(n, cx + min_sep)
        used_mask[y0:y1, x0:x1] = True

    rows = []
    for i, (ry, cx) in enumerate(candidates):
        rows.append({
            "site_id": f"Site-{chr(65 + i)}",
            "row": int(ry),
            "col": int(cx),
            "ice_likelihood_pct": round(max(0.0, float(ice_avg[ry, cx] * 100)), 1),
            "slope_deg": round(float(slope_avg[ry, cx]), 1),
            "roughness": round(float(rough_avg[ry, cx]), 2),
            "solar_hours": round(float(solar_avg[ry, cx]), 1),
            "distance_to_ice_px": round(float(dists[ry, cx]), 1),
            "distance_to_ice_m": round(float(dists[ry, cx] * scene["meta"]["pixel_size_m"]), 1),
        })
    return pd.DataFrame(rows)


def _normalize(series, higher_is_better=True):
    lo, hi = series.min(), series.max()
    if hi - lo < 1e-9:
        return pd.Series(np.full(len(series), 0.5), index=series.index)
    norm = (series - lo) / (hi - lo)
    return norm if higher_is_better else 1 - norm


def score_sites(candidates: pd.DataFrame, profile: str) -> pd.DataFrame:
    """Apply a mission profile's weights to produce a 0-100 suitability score
    per candidate site, plus a per-factor contribution breakdown for
    explainability.
    """
    weights = PROFILES[profile]
    df = candidates.copy()

    norm_ice = _normalize(df["ice_likelihood_pct"], higher_is_better=True)
    norm_slope = _normalize(df["slope_deg"], higher_is_better=False)
    norm_solar = _normalize(df["solar_hours"], higher_is_better=True)
    norm_rough = _normalize(df["roughness"], higher_is_better=False)
    norm_dist = _normalize(df["distance_to_ice_m"], higher_is_better=False)

    df["contrib_ice"] = norm_ice * weights["ice"] * 100
    df["contrib_slope"] = norm_slope * weights["slope"] * 100
    df["contrib_solar"] = norm_solar * weights["solar"] * 100
    df["contrib_roughness"] = norm_rough * weights["roughness"] * 100
    df["contrib_distance"] = norm_dist * weights["distance"] * 100

    df["suitability_score"] = (
        df["contrib_ice"] + df["contrib_slope"] + df["contrib_solar"]
        + df["contrib_roughness"] + df["contrib_distance"]
    ).round(1)

    df["mission_profile"] = profile
    df = df.sort_values("suitability_score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df


def trade_off_note(row: pd.Series, candidates: pd.DataFrame) -> str:
    """Human-readable trade-off summary for a scored site, described relative
    to the other candidates in the same shortlist (rank-based, not a fixed
    absolute threshold). This matters because "safe slope" or "ample solar"
    are meaningless in isolation -- what a mission planner needs to know is
    how a site compares to its alternatives on the shortlist.
    """
    n = len(candidates)

    def rank_note(col, label_high, label_low, higher_is_better, unit="", fmt="{:.1f}"):
        rank = int((candidates[col] > row[col]).sum()) + 1 if higher_is_better else \
               int((candidates[col] < row[col]).sum()) + 1
        value = fmt.format(row[col])
        if rank == 1:
            return f"{label_high} in shortlist ({value}{unit})"
        if rank == n:
            return f"{label_low} in shortlist ({value}{unit})"
        return None

    notes = []

    ice_note = rank_note("ice_likelihood_pct", "highest ice-proximity score", "lowest ice-proximity score",
                          higher_is_better=True, unit="%")
    if ice_note:
        notes.append(ice_note)

    slope_note = rank_note("slope_deg", "gentlest slope (safest)", "steepest slope (least safe)",
                            higher_is_better=False, unit=" deg")
    if slope_note:
        notes.append(slope_note)

    solar_note = rank_note("solar_hours", "most solar power available", "tightest solar power budget",
                            higher_is_better=True, unit=" h/day")
    if solar_note:
        notes.append(solar_note)

    dist_note = rank_note("distance_to_ice_m", "shortest rover traverse required", "longest rover traverse required",
                           higher_is_better=False, unit=" m", fmt="{:.0f}")
    if dist_note:
        notes.append(dist_note)

    if not notes:
        notes.append("mid-pack on all factors relative to the other candidates")

    return "; ".join(notes)


if __name__ == "__main__":
    from selene_ai.data_simulator import simulate_crater_scene
    from selene_ai.feature_extraction import extract_features
    from selene_ai.ice_estimation import estimate_ice_likelihood

    scene = simulate_crater_scene()
    df = extract_features(scene)
    df_ice, _ = estimate_ice_likelihood(df)
    cands = generate_candidate_sites(scene, df_ice)
    print(cands)
    for profile in PROFILES:
        scored = score_sites(cands, profile)
        print(f"\n=== {profile} ===")
        print(scored[["site_id", "suitability_score", "rank"]])
