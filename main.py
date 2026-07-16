"""
main.py
========
Runs the full SELENE-AI pipeline end-to-end on a simulated doubly-shadowed
crater scene and writes all outputs to ./outputs/:

  outputs/
    mission_report.md          <- Mission Intelligence Report (Markdown)
    static_panel.png           <- Multi-panel static figure for slides/report
    dashboard.html             <- Interactive Plotly dashboard
    ranked_sites_<profile>.csv <- Ranked site tables per mission profile
    rover_path.json            <- Rover traverse plan (waypoints + costs)
    pixel_features.csv         <- Full per-pixel feature/ice-likelihood table

Run: python3 main.py
"""

import json
import time
import pandas as pd

from selene_ai.data_simulator import simulate_crater_scene
from selene_ai.feature_extraction import extract_features, false_positive_reduction_stats
from selene_ai.ice_estimation import estimate_ice_likelihood
from selene_ai.mission_scoring import generate_candidate_sites, score_sites, PROFILES
from selene_ai.rover_planning import plan_traverse
from selene_ai.validation import validate
from selene_ai.visualization import make_static_panel, make_interactive_dashboard
from selene_ai.report import generate_report

OUT_DIR = "outputs"


def main():
    t0 = time.time()
    print("=" * 70)
    print("SELENE-AI - Integrated AI Mission Decision Support System")
    print("Lunar Ice Detection, Landing Site Selection & Rover Planning")
    print("=" * 70)

    print("\n[Stage 0] Simulating scene (stand-in for Chandrayaan-2 DFSAR + OHRC)...")
    scene = simulate_crater_scene()

    print("[Stage 1] Feature extraction + m-chi decomposition...")
    df = extract_features(scene)
    fp_stats = false_positive_reduction_stats(df)
    print(f"          CPR-only footprint: {fp_stats['cpr_only_pixel_count']} px | "
          f"Triple-evidence footprint: {fp_stats['triple_evidence_pixel_count']} px | "
          f"Reduction: {fp_stats['area_reduction_pct']}%")

    print("[Stage 2] Ice likelihood estimation (Random Forest + bootstrap uncertainty)...")
    df_ice, rf_model = estimate_ice_likelihood(df)

    print("[Stage 3] Generating candidate landing sites...")
    candidates = generate_candidate_sites(scene, df_ice, n_candidates=6)
    print(f"          {len(candidates)} candidate sites identified.")

    print("[Stage 4] Scoring & ranking sites across 3 mission profiles...")
    candidates_by_profile = {p: score_sites(candidates, p) for p in PROFILES}
    for p, dfp in candidates_by_profile.items():
        top = dfp.iloc[0]
        print(f"          {p:15s} -> top site: {top['site_id']} (score {top['suitability_score']})")

    print("[Stage 5] Energy-aware rover traverse planning...")
    balanced_top = candidates_by_profile["balanced"].iloc[0]
    n = scene["meta"]["grid_size"]
    start_rc = (int(balanced_top["row"]), int(balanced_top["col"]))
    # target: highest ice-likelihood pixel on the shadowed floor
    ice_grid = df_ice["ice_likelihood_pct"].values.reshape(n, n)
    import numpy as np
    floor = scene["floor_mask"].astype(bool)
    masked_ice = np.where(floor, ice_grid, -1)
    target_rc = tuple(int(v) for v in np.unravel_index(np.argmax(masked_ice), masked_ice.shape))
    rover_result = plan_traverse(scene, start_rc, target_rc)
    if rover_result["feasible"]:
        print(f"          Path found: {rover_result['total_distance_m']} m, "
              f"energy cost {rover_result['total_energy_cost']}")
    else:
        print(f"          No path: {rover_result['reason']}")

    print("[Validation] Running validation checks...")
    checks = validate(scene, df, fp_stats)
    for c in checks:
        status = "PASS" if c["passed"] else ("N/A" if c["passed"] is None else "FAIL")
        print(f"          [{status}] {c['check']}: {c['result_pct']}")

    print("\n[Output] Writing artifacts to ./outputs/ ...")
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

    df_ice.drop(columns=["_model_feature_importance"], errors="ignore").to_csv(
        f"{OUT_DIR}/pixel_features.csv", index=False
    )
    for p, dfp in candidates_by_profile.items():
        dfp.to_csv(f"{OUT_DIR}/ranked_sites_{p}.csv", index=False)

    with open(f"{OUT_DIR}/rover_path.json", "w") as f:
        json.dump(rover_result, f, indent=2, default=str)

    make_static_panel(scene, df_ice, candidates_by_profile["balanced"], rover_result,
                       f"{OUT_DIR}/static_panel.png")
    make_interactive_dashboard(scene, df_ice, candidates_by_profile, rover_result,
                                f"{OUT_DIR}/dashboard.html")
    generate_report(scene, fp_stats, candidates_by_profile, rover_result, checks,
                     f"{OUT_DIR}/mission_report.md")

    print(f"\nDone in {time.time() - t0:.1f}s. Outputs written to ./{OUT_DIR}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
