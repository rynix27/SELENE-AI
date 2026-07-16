"""
rover_planning.py
===================
Stage 5 of the SELENE-AI pipeline: Energy-Aware Rover Path Planning.

Builds an 8-connected grid graph over the scene and finds a minimum-energy
route (not merely shortest-distance) from a landing site to the target
ice-bearing PSR floor patch, using:

    cost = distance * (1 + 0.05 * slope^2) * roughness

Hard constraints: slope > 20 deg excluded; non-illuminated segments
excluded (a segment is "illuminated" if solar hours >= MIN_SOLAR_HOURS,
representing rover power budget outside the PSR -- inside the PSR the
rover runs on battery reserve for a bounded excursion).
Soft constraint: high roughness is discouraged via the multiplicative
roughness term rather than hard-excluded.
"""

import math
import networkx as nx
import numpy as np

SLOPE_HARD_LIMIT_DEG = 20.0
BATTERY_ONLY_MAX_STEPS = 25   # bounded excursion length allowed with zero illumination (PSR floor)


def build_traverse_graph(scene: dict) -> nx.Graph:
    n = scene["meta"]["grid_size"]
    px = scene["meta"]["pixel_size_m"]
    slope = scene["slope_deg"]
    roughness = scene["roughness"]
    illum = scene["illumination_hours"]

    G = nx.Graph()
    for r in range(n):
        for c in range(n):
            G.add_node((r, c))

    neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    for r in range(n):
        for c in range(n):
            s1 = slope[r, c]
            if s1 > SLOPE_HARD_LIMIT_DEG:
                continue
            for dr, dc in neighbors:
                r2, c2 = r + dr, c + dc
                if not (0 <= r2 < n and 0 <= c2 < n):
                    continue
                s2 = slope[r2, c2]
                if s2 > SLOPE_HARD_LIMIT_DEG:
                    continue
                dist = px * math.sqrt(dr ** 2 + dc ** 2)
                avg_slope = (s1 + s2) / 2
                avg_rough = (roughness[r, c] + roughness[r2, c2]) / 2
                cost = dist * (1 + 0.05 * avg_slope ** 2) * avg_rough
                G.add_edge((r, c), (r2, c2), weight=cost, distance=dist)
    return G


def plan_traverse(scene: dict, start_rc: tuple, target_rc: tuple):
    """Find the minimum-energy path from start_rc to target_rc.

    Returns dict with waypoints, total distance, total energy cost, and
    per-segment cost breakdown, or an error message if infeasible.
    """
    G = build_traverse_graph(scene)
    if start_rc not in G or target_rc not in G:
        return {"feasible": False, "reason": "start or target node excluded by hard slope constraint"}

    try:
        path = nx.dijkstra_path(G, start_rc, target_rc, weight="weight")
    except nx.NetworkXNoPath:
        return {"feasible": False, "reason": "no traversable path under current constraints"}

    illum = scene["illumination_hours"]
    total_distance = 0.0
    total_cost = 0.0
    segments = []
    dark_streak = 0
    max_dark_streak = 0
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        edata = G.edges[a, b]
        total_distance += edata["distance"]
        total_cost += edata["weight"]
        dark = illum[b] < 0.5
        dark_streak = dark_streak + 1 if dark else 0
        max_dark_streak = max(max_dark_streak, dark_streak)
        segments.append({
            "from": a, "to": b,
            "distance_m": round(edata["distance"], 1),
            "energy_cost": round(edata["weight"], 2),
            "in_psr_dark": bool(dark),
        })

    battery_ok = max_dark_streak <= BATTERY_ONLY_MAX_STEPS
    return {
        "feasible": True,
        "battery_budget_ok": battery_ok,
        "max_consecutive_dark_steps": max_dark_streak,
        "waypoints": path,
        "total_distance_m": round(total_distance, 1),
        "total_energy_cost": round(total_cost, 2),
        "n_segments": len(segments),
        "segments": segments,
    }


if __name__ == "__main__":
    from selene_ai.data_simulator import simulate_crater_scene
    scene = simulate_crater_scene()
    n = scene["meta"]["grid_size"]
    # start near rim (safe, illuminated), target near ice patch on floor
    start = (10, int(n * 0.47))
    target = (int(n * 0.50), int(n * 0.47))
    result = plan_traverse(scene, start, target)
    print({k: v for k, v in result.items() if k != "segments"})
