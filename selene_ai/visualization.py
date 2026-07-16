"""
visualization.py
==================
Produces:
  1. A static multi-panel PNG (CPR, DOP, ice likelihood, candidate sites,
     rover path overlay) for the report / slide deck.
  2. An interactive Plotly HTML dashboard for live demo.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def make_static_panel(scene, df_ice, candidates_scored, rover_result, out_path):
    n = scene["meta"]["grid_size"]
    ice_grid = df_ice["ice_likelihood_pct"].values.reshape(n, n)

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle("SELENE-AI - Mission Intelligence Panel (Simulated Crater Scene)", fontsize=14, fontweight="bold")

    panels = [
        ("elevation_m", "Elevation (m)", "terrain"),
        ("cpr", "CPR (Circular Polarization Ratio)", "viridis"),
        ("dop", "DOP (Degree of Polarization)", "plasma"),
        ("slope_deg", "Slope (deg)", "inferno"),
        ("roughness", "Roughness", "cividis"),
    ]
    for ax, (key, title, cmap) in zip(axes.flat[:5], panels):
        im = ax.imshow(scene[key], cmap=cmap, origin="upper")
        ax.set_title(title, fontsize=10)
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes.flat[5]
    im = ax.imshow(ice_grid, cmap="Blues", origin="upper", vmin=0, vmax=100)
    ax.set_title("Ice Likelihood (%) + Candidate Sites + Rover Path", fontsize=10)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    for _, row in candidates_scored.iterrows():
        color = "red" if row["rank"] == 1 else "orange"
        ax.scatter(row["col"], row["row"], c=color, s=60, edgecolors="white", linewidths=0.8, zorder=5)
        ax.annotate(row["site_id"], (row["col"], row["row"]), color="white", fontsize=7,
                    xytext=(3, 3), textcoords="offset points")

    if rover_result.get("feasible"):
        wp = np.array(rover_result["waypoints"])
        ax.plot(wp[:, 1], wp[:, 0], color="lime", linewidth=1.8, zorder=4, label="Rover path")
        ax.legend(loc="lower right", fontsize=7)
    ax.axis("off")

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_interactive_dashboard(scene, df_ice, candidates_scored_by_profile: dict, rover_result, out_path):
    n = scene["meta"]["grid_size"]
    ice_grid = df_ice["ice_likelihood_pct"].values.reshape(n, n)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("CPR (raw radar signature)", "Ice Likelihood (%) with candidate sites & rover path"),
        horizontal_spacing=0.08,
    )
    fig.add_trace(go.Heatmap(z=scene["cpr"], colorscale="Viridis", showscale=True, name="CPR"), row=1, col=1)
    fig.add_trace(go.Heatmap(z=ice_grid, colorscale="Blues", zmin=0, zmax=100, showscale=True, name="Ice %"), row=1, col=2)

    balanced = candidates_scored_by_profile["balanced"]
    fig.add_trace(
        go.Scatter(
            x=balanced["col"], y=balanced["row"], mode="markers+text",
            text=balanced["site_id"], textposition="top center",
            marker=dict(size=12, color=balanced["suitability_score"], colorscale="Reds", showscale=False,
                        line=dict(width=1, color="white")),
            name="Candidate sites (Balanced profile)",
        ),
        row=1, col=2,
    )

    if rover_result.get("feasible"):
        wp = np.array(rover_result["waypoints"])
        fig.add_trace(
            go.Scatter(x=wp[:, 1], y=wp[:, 0], mode="lines", line=dict(color="lime", width=3),
                       name="Rover traverse path"),
            row=1, col=2,
        )

    fig.update_yaxes(autorange="reversed", row=1, col=1)
    fig.update_yaxes(autorange="reversed", row=1, col=2)
    fig.update_layout(
        title="SELENE-AI Mission Dashboard - Simulated Doubly-Shadowed Crater",
        height=560, width=1150, template="plotly_dark",
    )
    fig.write_html(out_path, include_plotlyjs="cdn")
    return out_path
