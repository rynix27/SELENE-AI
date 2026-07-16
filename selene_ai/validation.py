"""
validation.py
===============
Implements the validation strategy from the technical brief, adapted to run
against the synthetic scene (since real Chandrayaan-1 Mini-RF / LOLA products
aren't loaded in this prototype). Each check is clearly labeled with what a
real-data validation run would compare against.
"""

import numpy as np
import pandas as pd


def validate(scene: dict, df_features: pd.DataFrame, fp_stats: dict) -> list:
    checks = []

    # 1. "CPR consistency" -- here: overlap of triple-evidence detections with
    #    the synthetic ground-truth ice patch (stand-in for Mini-RF anomaly overlap)
    true_mask = df_features["_true_ice_patch"] > 0.3
    detect_mask = df_features["triple_evidence_ice_flag"]
    if true_mask.sum() > 0:
        overlap_pct = 100.0 * (true_mask & detect_mask).sum() / true_mask.sum()
    else:
        overlap_pct = 0.0
    checks.append({
        "check": "Spatial overlap with reference ice zone",
        "note": "Stand-in for Chandrayaan-1 Mini-RF anomaly comparison (real run: compare vs. published Mini-RF CPR anomaly maps)",
        "result_pct": round(overlap_pct, 1),
        "target": ">70% spatial overlap",
        "passed": overlap_pct > 70,
    })

    # 2. PSR compliance: all triple-evidence detections must fall within the
    #    permanently shadowed region (is_psr)
    if detect_mask.sum() > 0:
        psr_compliance = 100.0 * df_features.loc[detect_mask, "is_psr"].mean()
    else:
        psr_compliance = 100.0
    checks.append({
        "check": "PSR compliance of detected ice pixels",
        "note": "Real run: verify against LOLA-derived PSR boundary polygons",
        "result_pct": round(psr_compliance, 1),
        "target": "100% within confirmed PSRs",
        "passed": psr_compliance >= 99.9,
    })

    # 3. Baseline comparison: CPR-only vs triple-evidence area reduction
    checks.append({
        "check": "False-positive area reduction vs. CPR-only baseline",
        "note": "Triple-evidence (CPR + m-chi + PSR) vs. naive CPR > 1.0 thresholding",
        "result_pct": fp_stats["area_reduction_pct"],
        "target": "Reduction in false-positive area (higher is better)",
        "passed": fp_stats["area_reduction_pct"] > 0,
    })

    # 4. Literature match -- documented as a manual step for the real system;
    #    flagged here as informational since the synthetic scene has no named craters.
    checks.append({
        "check": "Literature match vs. known priority craters",
        "note": "Real run: compare top-ranked sites vs. Haworth, Shackleton, Faustini priority list",
        "result_pct": None,
        "target": "2+ of top 3 match named priority craters",
        "passed": None,
    })

    return checks


if __name__ == "__main__":
    from selene_ai.data_simulator import simulate_crater_scene
    from selene_ai.feature_extraction import extract_features, false_positive_reduction_stats

    scene = simulate_crater_scene()
    df = extract_features(scene)
    fp_stats = false_positive_reduction_stats(df)
    for c in validate(scene, df, fp_stats):
        print(c)
