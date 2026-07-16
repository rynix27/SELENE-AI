"""
export_web_data.py
=====================
Runs the full SELENE-AI pipeline and serializes every real, computed result
(grids, ranked sites per profile, rover path, validation, false-positive
stats) into a single JSON file for the website front end. No numbers in the
website are hand-authored -- everything traces back to this export.
"""

import json
import numpy as np

from selene_ai.data_simulator import simulate_crater_scene
from selene_ai.feature_extraction import extract_features, false_positive_reduction_stats
from selene_ai.ice_estimation import estimate_ice_likelihood
from selene_ai.mission_scoring import generate_candidate_sites, score_sites, trade_off_note, PROFILES
from selene_ai.rover_planning import plan_traverse
from selene_ai.validation import validate


def _json_safe(obj):
    """Recursively convert numpy scalar types to native Python types."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


def round_grid(arr, decimals=3):
    return np.round(arr.astype(float), decimals).tolist()


def main(out_path="outputs/website_data.json"):
    scene = simulate_crater_scene()
    df = extract_features(scene)
    fp_stats = false_positive_reduction_stats(df)
    df_ice, rf_model = estimate_ice_likelihood(df)

    n = scene["meta"]["grid_size"]
    ice_grid = df_ice["ice_likelihood_pct"].values.reshape(n, n)

    candidates = generate_candidate_sites(scene, df_ice, n_candidates=6)
    candidates_by_profile = {p: score_sites(candidates, p) for p in PROFILES}

    balanced_top = candidates_by_profile["balanced"].iloc[0]
    floor = scene["floor_mask"].astype(bool)
    masked_ice = np.where(floor, ice_grid, -1)
    target_rc = tuple(int(v) for v in np.unravel_index(np.argmax(masked_ice), masked_ice.shape))
    start_rc = (int(balanced_top["row"]), int(balanced_top["col"]))
    rover_result = plan_traverse(scene, start_rc, target_rc)

    checks = validate(scene, df, fp_stats)

    feature_importance = None
    if hasattr(rf_model, "feature_importances_"):
        from selene_ai.ice_estimation import FEATURE_COLUMNS
        feature_importance = {k: round(float(v), 4) for k, v in
                               zip(FEATURE_COLUMNS, rf_model.feature_importances_)}

    def sites_payload(df_scored, profile_name):
        out = []
        for _, row in df_scored.iterrows():
            out.append({
                "site_id": row["site_id"],
                "row": int(row["row"]),
                "col": int(row["col"]),
                "rank": int(row["rank"]),
                "score": float(row["suitability_score"]),
                "ice_pct": float(row["ice_likelihood_pct"]),
                "slope_deg": float(row["slope_deg"]),
                "roughness": float(row["roughness"]),
                "solar_hours": float(row["solar_hours"]),
                "distance_to_ice_m": float(row["distance_to_ice_m"]),
                "contrib": {
                    "ice": round(float(row["contrib_ice"]), 1),
                    "slope": round(float(row["contrib_slope"]), 1),
                    "solar": round(float(row["contrib_solar"]), 1),
                    "roughness": round(float(row["contrib_roughness"]), 1),
                    "distance": round(float(row["contrib_distance"]), 1),
                },
                "trade_off": trade_off_note(row, df_scored),
            })
        return out

    payload = {
        "meta": {
            "crater_name": scene["meta"]["crater_name"],
            "source": scene["meta"]["source"],
            "grid_size": n,
            "pixel_size_m": scene["meta"]["pixel_size_m"],
        },
        "grids": {
            "cpr": round_grid(scene["cpr"]),
            "dop": round_grid(scene["dop"]),
            "slope_deg": round_grid(scene["slope_deg"]),
            "roughness": round_grid(scene["roughness"]),
            "elevation_m": round_grid(scene["elevation_m"]),
            "illumination_hours": round_grid(scene["illumination_hours"]),
            "ice_likelihood_pct": round_grid(ice_grid),
            "floor_mask": round_grid(scene["floor_mask"]),
        },
        "fp_stats": fp_stats,
        "profiles": {
            "science_first": {
                "weights": PROFILES["science_first"],
                "sites": sites_payload(candidates_by_profile["science_first"], "science_first"),
            },
            "safety_first": {
                "weights": PROFILES["safety_first"],
                "sites": sites_payload(candidates_by_profile["safety_first"], "safety_first"),
            },
            "balanced": {
                "weights": PROFILES["balanced"],
                "sites": sites_payload(candidates_by_profile["balanced"], "balanced"),
            },
        },
        "rover": {
            "feasible": rover_result.get("feasible"),
            "start_rc": list(start_rc),
            "target_rc": list(target_rc),
            "total_distance_m": rover_result.get("total_distance_m"),
            "total_energy_cost": rover_result.get("total_energy_cost"),
            "n_segments": rover_result.get("n_segments"),
            "max_consecutive_dark_steps": rover_result.get("max_consecutive_dark_steps"),
            "battery_budget_ok": rover_result.get("battery_budget_ok"),
            "waypoints": rover_result.get("waypoints", []),
        },
        "validation": checks,
        "feature_importance": feature_importance,
    }

    with open(out_path, "w") as f:
        json.dump(_json_safe(payload), f)

    import os
    print(f"Wrote {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")
    return payload


if __name__ == "__main__":
    main()
