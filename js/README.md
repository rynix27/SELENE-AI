# rover_planning.js

A dependency-free JavaScript/Node.js port of `selene_ai/rover_planning.py`
(Stage 5 of the SELENE-AI pipeline: energy-aware rover traverse planning).

It reimplements the same 8-connected grid graph + Dijkstra minimum-energy
search as the Python version (which uses `networkx`), but with a hand-rolled
binary-heap priority queue and no external packages.

## Usage

```bash
node rover_planning.js sample_scene.json
```

or import it as a module:

```js
const { planTraverse } = require('./rover_planning.js');

const result = planTraverse(scene, [10, 37], [40, 37]);
console.log(result.total_distance_m, result.total_energy_cost);
```

`scene` must have the shape:

```js
{
  meta: { grid_size: 80, pixel_size_m: 20.0 },
  slope_deg: number[][],          // [row][col], length = grid_size
  roughness: number[][],
  illumination_hours: number[][],
}
```

`sample_scene.json` in this folder is a real exported scene (from
`selene_ai/data_simulator.py`) you can use to try it immediately.

## Verified against the Python original

Run against the same sample scene, this port produces byte-for-byte
identical results to `rover_planning.py`: same waypoints, same
`total_distance_m` (777.4), same `total_energy_cost` (839.16), same
per-segment distance/energy breakdown, and the same
`max_consecutive_dark_steps` (12).
