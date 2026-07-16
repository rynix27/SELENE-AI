"""
ice_estimation.py
==================
Stage 2 of the SELENE-AI pipeline: Ice Likelihood Estimation.

Since no ground-truth ice samples exist for the lunar south pole, SELENE-AI
uses a semi-supervised approach: pseudo-labels are drawn from the
triple-evidence physical detector (Stage 1) as weak/noisy supervision
("spatial priors from published PSR maps" in the technical brief), and a
Random Forest is trained to generalize a smooth, interpretable ice
likelihood surface with per-pixel uncertainty from bootstrap aggregation
across the forest's trees.

Output: ice_likelihood (0-100%) and a confidence interval per pixel/site,
e.g. "Region has 84% ice probability +/-9% confidence range."
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

FEATURE_COLUMNS = [
    "cpr", "dop", "surface_power", "volume_power", "double_bounce_power",
    "slope_deg", "roughness", "illumination_hours",
]


def estimate_ice_likelihood(df: pd.DataFrame, n_estimators: int = 200, seed: int = 7) -> pd.DataFrame:
    """Train a Random Forest on Stage-1 pseudo-labels and produce per-pixel
    ice likelihood (%) with a 90% bootstrap confidence interval.
    """
    X = df[FEATURE_COLUMNS].values
    y = df["triple_evidence_ice_flag"].astype(int).values

    if y.sum() < 5:
        # guard: not enough positive pseudo-labels to train meaningfully
        df = df.copy()
        df["ice_likelihood_pct"] = df["triple_evidence_ice_flag"].astype(float) * 100
        df["ice_ci_low_pct"] = df["ice_likelihood_pct"]
        df["ice_ci_high_pct"] = df["ice_likelihood_pct"]
        return df

    rf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=8,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
    )
    rf.fit(X, y)

    # Per-tree predicted probability -> distribution per pixel -> CI
    tree_probs = np.stack(
        [tree.predict_proba(X)[:, 1] if 1 in tree.classes_ else np.zeros(len(X))
         for tree in rf.estimators_],
        axis=0,
    )  # shape (n_trees, n_pixels)

    mean_prob = tree_probs.mean(axis=0)
    ci_low = np.percentile(tree_probs, 5, axis=0)
    ci_high = np.percentile(tree_probs, 95, axis=0)

    out = df.copy()
    out["ice_likelihood_pct"] = np.round(mean_prob * 100, 1)
    out["ice_ci_low_pct"] = np.round(ci_low * 100, 1)
    out["ice_ci_high_pct"] = np.round(ci_high * 100, 1)
    out["_model_feature_importance"] = [dict(zip(FEATURE_COLUMNS, rf.feature_importances_))] * len(out)
    return out, rf


def summarize_region(df: pd.DataFrame, mask: np.ndarray, label: str) -> dict:
    """Summarize ice likelihood over a boolean pixel mask (e.g. a candidate site)."""
    sub = df.loc[mask]
    if len(sub) == 0:
        return {"region": label, "mean_ice_pct": 0.0, "ci_low_pct": 0.0, "ci_high_pct": 0.0, "n_pixels": 0}
    return {
        "region": label,
        "mean_ice_pct": round(float(sub["ice_likelihood_pct"].mean()), 1),
        "ci_low_pct": round(float(sub["ice_ci_low_pct"].mean()), 1),
        "ci_high_pct": round(float(sub["ice_ci_high_pct"].mean()), 1),
        "n_pixels": int(len(sub)),
    }


if __name__ == "__main__":
    from selene_ai.data_simulator import simulate_crater_scene
    from selene_ai.feature_extraction import extract_features

    scene = simulate_crater_scene()
    df = extract_features(scene)
    out, rf = estimate_ice_likelihood(df)
    print(out[["row", "col", "ice_likelihood_pct", "ice_ci_low_pct", "ice_ci_high_pct"]].sample(5, random_state=1))
    print("Feature importances:", dict(zip(FEATURE_COLUMNS, rf.feature_importances_)))
