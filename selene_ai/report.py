"""
report.py
==========
Assembles the final "Mission Intelligence Report" (Stage output) as Markdown:
ranked sites per profile, trade-off notes, rover traverse summary, validation
results, and honest limitations -- ready to paste into a writeup or convert
to PDF/DOCX.
"""

from datetime import datetime
from selene_ai.mission_scoring import trade_off_note


def generate_report(scene, fp_stats, candidates_by_profile, rover_result, validation_checks, out_path):
    lines = []
    lines.append("# SELENE-AI - Mission Intelligence Report")
    lines.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | Scene: {scene['meta']['crater_name']}*")
    lines.append(f"*Data source: {scene['meta']['source']}*\n")

    lines.append("## 1. Ice Detection Summary")
    lines.append(f"- CPR-only (naive) detection footprint: **{fp_stats['cpr_only_pixel_count']} px**")
    lines.append(f"- Triple-evidence (CPR + m-chi + PSR) detection footprint: **{fp_stats['triple_evidence_pixel_count']} px**")
    lines.append(f"- False-positive area reduction: **{fp_stats['area_reduction_pct']}%**")
    lines.append(f"- Rough-terrain false positives removed: **{fp_stats['rough_terrain_false_positives_removed']} px**\n")

    lines.append("## 2. Ranked Landing Sites by Mission Profile\n")
    for profile, df in candidates_by_profile.items():
        lines.append(f"### Profile: {profile.replace('_', ' ').title()}")
        lines.append("| Rank | Site | Score | Ice % | Slope\u00b0 | Solar h | Dist. to ice (m) | Trade-off |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for _, row in df.iterrows():
            lines.append(
                f"| {row['rank']} | {row['site_id']} | {row['suitability_score']} | "
                f"{row['ice_likelihood_pct']} | {row['slope_deg']} | {row['solar_hours']} | "
                f"{row['distance_to_ice_m']} | {trade_off_note(row, df)} |"
            )
        lines.append("")

    lines.append("## 3. Rover Traverse Plan")
    if rover_result.get("feasible"):
        lines.append(f"- Feasible path found: **{rover_result['n_segments']} segments**")
        lines.append(f"- Total distance: **{rover_result['total_distance_m']} m**")
        lines.append(f"- Total relative energy cost: **{rover_result['total_energy_cost']}**")
        lines.append(f"- Max consecutive dark (battery-only) steps: **{rover_result['max_consecutive_dark_steps']}** "
                      f"({'within' if rover_result['battery_budget_ok'] else 'EXCEEDS'} battery budget)")
    else:
        lines.append(f"- **No feasible path found**: {rover_result.get('reason')}")
    lines.append("")

    lines.append("## 4. Validation Results")
    lines.append("| Check | Result | Target | Passed |")
    lines.append("|---|---|---|---|")
    for c in validation_checks:
        result = f"{c['result_pct']}%" if c["result_pct"] is not None else "N/A (manual step)"
        if c["passed"] is None:
            passed = "N/A"
        elif c["passed"]:
            passed = "PASS"
        else:
            passed = "FAIL"
        lines.append(f"| {c['check']} | {result} | {c['target']} | {passed} |")
        lines.append(f"| | *{c['note']}* | | |")
    lines.append("")

    lines.append("## 5. Honest Limitations")
    lines.append("- CPR anomalies are ice-consistent, not ice-proven; m-chi decomposition reduces but does not eliminate ambiguity.")
    lines.append("- No ground truth exists for the real lunar south pole; this prototype run uses a **synthetic scene** "
                  "as a stand-in for Chandrayaan-2 DFSAR/OHRC products (swap in real ISSDC data via `data_simulator.load_real_dfsar()`).")
    lines.append("- Slope estimates carry \u00b13\u00b0 uncertainty in the real system; should be cross-validated with LOLA DEM.")
    lines.append("- The rover energy model is relative (for route comparison), not an absolute power budget in Wh.")
    lines.append("")
    lines.append("---\n*SELENE-AI: Mission Intelligence from Chandrayaan-2 Data*")

    text = "\n".join(lines)
    with open(out_path, "w") as f:
        f.write(text)
    return out_path
