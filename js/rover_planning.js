/**
 * rover_planning.js
 * ===================
 * JavaScript/Node.js port of selene_ai/rover_planning.py.
 *
 * Stage 5 of the SELENE-AI pipeline: Energy-Aware Rover Path Planning.
 *
 * Builds an 8-connected grid graph over the scene and finds a minimum-energy
 * route (not merely shortest-distance) from a landing site to the target
 * ice-bearing PSR floor patch, using:
 *
 *     cost = distance * (1 + 0.05 * slope^2) * roughness
 *
 * Hard constraints: slope > 20 deg excluded; non-illuminated segments
 * excluded (a segment is "illuminated" if solar hours >= MIN_SOLAR_HOURS,
 * representing rover power budget outside the PSR -- inside the PSR the
 * rover runs on battery reserve for a bounded excursion).
 * Soft constraint: high roughness is discouraged via the multiplicative
 * roughness term rather than hard-excluded.
 *
 * Input `scene` shape (matches the Python data_simulator output, minus the
 * fields this module doesn't need):
 *   {
 *     meta: { grid_size: number, pixel_size_m: number },
 *     slope_deg: number[][],          // [row][col]
 *     roughness: number[][],
 *     illumination_hours: number[][],
 *   }
 *
 * No external dependencies -- Dijkstra is implemented here with a binary
 * min-heap instead of relying on a graph library (the Python version uses
 * networkx).
 */

'use strict';

const SLOPE_HARD_LIMIT_DEG = 20.0;
const BATTERY_ONLY_MAX_STEPS = 25; // bounded excursion length allowed with zero illumination (PSR floor)

const NEIGHBORS = [
  [-1, 0], [1, 0], [0, -1], [0, 1],
  [-1, -1], [-1, 1], [1, -1], [1, 1],
];

/** Binary min-heap keyed on a numeric priority. */
class MinHeap {
  constructor() {
    this._items = []; // [{ priority, value }]
  }

  get size() {
    return this._items.length;
  }

  push(priority, value) {
    const items = this._items;
    items.push({ priority, value });
    let i = items.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (items[parent].priority <= items[i].priority) break;
      [items[parent], items[i]] = [items[i], items[parent]];
      i = parent;
    }
  }

  pop() {
    const items = this._items;
    if (items.length === 0) return null;
    const top = items[0];
    const last = items.pop();
    if (items.length > 0) {
      items[0] = last;
      let i = 0;
      const n = items.length;
      for (;;) {
        const l = 2 * i + 1;
        const r = 2 * i + 2;
        let smallest = i;
        if (l < n && items[l].priority < items[smallest].priority) smallest = l;
        if (r < n && items[r].priority < items[smallest].priority) smallest = r;
        if (smallest === i) break;
        [items[i], items[smallest]] = [items[smallest], items[i]];
        i = smallest;
      }
    }
    return top;
  }
}

const key = (r, c) => `${r},${c}`;

/**
 * Build the traversal graph as an adjacency map:
 *   Map<"r,c", Array<{ r, c, weight, distance }>>
 * Nodes with slope above the hard limit are excluded entirely (mirrors the
 * Python version, which still adds every node to the graph but never gives
 * it edges -- here we simply never populate its adjacency list, which is
 * behaviorally equivalent for Dijkstra).
 */
function buildTraverseGraph(scene) {
  const n = scene.meta.grid_size;
  const px = scene.meta.pixel_size_m;
  const slope = scene.slope_deg;
  const roughness = scene.roughness;

  const adjacency = new Map();
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      adjacency.set(key(r, c), []);
    }
  }

  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      const s1 = slope[r][c];
      if (s1 > SLOPE_HARD_LIMIT_DEG) continue;

      for (const [dr, dc] of NEIGHBORS) {
        const r2 = r + dr;
        const c2 = c + dc;
        if (r2 < 0 || r2 >= n || c2 < 0 || c2 >= n) continue;

        const s2 = slope[r2][c2];
        if (s2 > SLOPE_HARD_LIMIT_DEG) continue;

        const dist = px * Math.sqrt(dr * dr + dc * dc);
        const avgSlope = (s1 + s2) / 2;
        const avgRough = (roughness[r][c] + roughness[r2][c2]) / 2;
        const cost = dist * (1 + 0.05 * avgSlope * avgSlope) * avgRough;

        // Undirected graph: add the edge from both sides once each
        // (each (r,c) iteration only adds its own outgoing edge, but since
        // every node is visited, the reverse edge gets added when we reach
        // (r2,c2) and look back at (r,c) via the same neighbor offsets).
        adjacency.get(key(r, c)).push({ r: r2, c: c2, weight: cost, distance: dist });
      }
    }
  }

  return adjacency;
}

/**
 * Dijkstra shortest (minimum-energy) path between two (row, col) nodes.
 * Returns { path: [[r,c], ...], edges: [{from,to,weight,distance}, ...] }
 * or null if no path exists.
 */
function dijkstraPath(adjacency, startKey, targetKey) {
  const dist = new Map([[startKey, 0]]);
  const prev = new Map();
  const visited = new Set();
  const heap = new MinHeap();
  heap.push(0, startKey);

  while (heap.size > 0) {
    const { priority, value: u } = heap.pop();
    if (visited.has(u)) continue;
    visited.add(u);
    if (u === targetKey) break;
    if (priority > (dist.get(u) ?? Infinity)) continue;

    const neighbors = adjacency.get(u);
    if (!neighbors) continue;

    const [ur, uc] = u.split(',').map(Number);
    for (const edge of neighbors) {
      const v = key(edge.r, edge.c);
      if (visited.has(v)) continue;
      const alt = priority + edge.weight;
      if (alt < (dist.get(v) ?? Infinity)) {
        dist.set(v, alt);
        prev.set(v, { node: u, weight: edge.weight, distance: edge.distance });
        heap.push(alt, v);
      }
    }
  }

  if (!dist.has(targetKey)) return null;

  const path = [];
  const edges = [];
  let cur = targetKey;
  while (cur !== startKey) {
    const p = prev.get(cur);
    if (!p) return null; // shouldn't happen if dist.has(targetKey)
    path.push(cur);
    edges.push({ from: p.node, to: cur, weight: p.weight, distance: p.distance });
    cur = p.node;
  }
  path.push(startKey);
  path.reverse();
  edges.reverse();

  return { path, edges };
}

/**
 * Find the minimum-energy path from startRc to targetRc.
 *
 * @param {object} scene   { meta: {grid_size, pixel_size_m}, slope_deg, roughness, illumination_hours }
 * @param {[number, number]} startRc  [row, col]
 * @param {[number, number]} targetRc [row, col]
 * @returns {object} Same shape as the Python `plan_traverse` return value.
 */
function planTraverse(scene, startRc, targetRc) {
  const adjacency = buildTraverseGraph(scene);
  const startKey = key(startRc[0], startRc[1]);
  const targetKey = key(targetRc[0], targetRc[1]);

  // Every (row, col) node is always present in the adjacency map (mirrors
  // the Python version, which adds every grid cell to the graph regardless
  // of slope); nodes excluded by the hard slope limit simply end up with
  // no edges, so Dijkstra naturally fails to route through/into them.
  const result = dijkstraPath(adjacency, startKey, targetKey);
  if (!result) {
    return { feasible: false, reason: 'no traversable path under current constraints' };
  }

  const illum = scene.illumination_hours;
  let totalDistance = 0;
  let totalCost = 0;
  let darkStreak = 0;
  let maxDarkStreak = 0;
  const segments = [];

  for (const edge of result.edges) {
    const [br, bc] = edge.to.split(',').map(Number);
    totalDistance += edge.distance;
    totalCost += edge.weight;
    const dark = illum[br][bc] < 0.5;
    darkStreak = dark ? darkStreak + 1 : 0;
    maxDarkStreak = Math.max(maxDarkStreak, darkStreak);

    const [ar, ac] = edge.from.split(',').map(Number);
    segments.push({
      from: [ar, ac],
      to: [br, bc],
      distance_m: round(edge.distance, 1),
      energy_cost: round(edge.weight, 2),
      in_psr_dark: dark,
    });
  }

  const waypoints = result.path.map((k) => k.split(',').map(Number));

  return {
    feasible: true,
    battery_budget_ok: maxDarkStreak <= BATTERY_ONLY_MAX_STEPS,
    max_consecutive_dark_steps: maxDarkStreak,
    waypoints,
    total_distance_m: round(totalDistance, 1),
    total_energy_cost: round(totalCost, 2),
    n_segments: segments.length,
    segments,
  };
}

function round(value, decimals) {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

module.exports = { planTraverse, buildTraverseGraph, SLOPE_HARD_LIMIT_DEG, BATTERY_ONLY_MAX_STEPS };

// --- CLI demo, mirrors the `if __name__ == "__main__"` block in rover_planning.py ---
if (require.main === module) {
  const fs = require('fs');
  const path = require('path');

  const scenePath = process.argv[2] || path.join(__dirname, 'sample_scene.json');
  const scene = JSON.parse(fs.readFileSync(scenePath, 'utf8'));

  const n = scene.meta.grid_size;
  // start near rim (safe, illuminated), target near ice patch on floor
  const start = [10, Math.floor(n * 0.47)];
  const target = [Math.floor(n * 0.50), Math.floor(n * 0.47)];

  const result = planTraverse(scene, start, target);
  const { segments, ...summary } = result;
  console.log(JSON.stringify(summary, null, 2));
  if (segments) console.log('n_segments', segments.length);
}
