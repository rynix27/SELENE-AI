# SELENE-AI
**S**ubsurface **E**xploration & **L**unar **EN**gineering **AI**
Integrated AI Mission Decision Support System for Lunar Ice Detection, Landing Site Selection & Rover Planning

*Detection and Characterization of Subsurface Ice in Lunar South Polar Regions Using Chandrayaan-2 Radar and Imagery Data for Landing Site and Rover Traverse Planning*

## What this is

A working, runnable implementation of the SELENE-AI pipeline. It runs
end-to-end in ~2 seconds and produces a full mission intelligence report,
ranked landing sites under three mission profiles, an energy-aware rover
traverse plan, validation checks, and both static and interactive
visualizations.

**Important - data honesty:** real Chandrayaan-2 DFSAR/OHRC data requires an
ISSDC PRADAN account and download, which isn't available in this environment.
`selene_ai/data_simulator.py` generates a physically-plausible **synthetic**
doubly-shadowed crater scene (CPR, DOP, m-chi decomposition components,
slope, roughness, illumination) that reproduces the exact problem the system
is designed to solve: rough terrain produces CPR signatures that look like
ice unless you also check volume-scattering dominance (m-chi) and PSR
location. Every module downstream is written against the *field names*, not
the synthetic generator - swap in real rasters and the rest of the pipeline
runs unchanged. See the "Data honesty" note in each module's docstring.

## Quick start

```bash
pip install -r requirements.txt
python3 main.py
```

Outputs land in `./outputs/`:

| File | Contents |
|---|---|
| `index.html` | **Interactive mission console website** &mdash; open directly in any browser, no server needed |
| `mission_report.md` | Full Mission Intelligence Report (ranked sites, trade-offs, rover plan, validation, limitations) |
| `static_panel.png` | 6-panel figure: elevation, CPR, DOP, slope, roughness, ice-likelihood+sites+rover path |
| `dashboard.html` | Interactive Plotly dashboard (open in any browser) |
| `website_data.json` | Raw data export consumed by `index.html` (regenerate with `python3 export_web_data.py`) |
| `ranked_sites_<profile>.csv` | Ranked candidate sites for each mission profile |
| `rover_path.json` | Full rover traverse plan: waypoints, per-segment energy cost, battery budget check |
| `pixel_features.csv` | Full per-pixel feature table (CPR, DOP, m-chi powers, ice likelihood, flags) |

## The website

`outputs/index.html` is a self-contained mission console: open it in any
browser, no server or build step required. It embeds the real output of
`export_web_data.py` (not hand-typed numbers) and lets you:

- switch between the three mission profiles and watch the ranked site table,
  map markers and weight bars update live
- toggle the crater map between seven real data layers (CPR, DOP, slope,
  roughness, elevation, illumination, ice likelihood) with per-pixel hover
  readouts
- see the actual rover traverse path drawn on the map, plus its
  elevation-along-path profile
- read the same validation results as the Markdown report, including the
  one check that currently fails

To regenerate it after changing the pipeline:

```bash
python3 build_website.py
```

This re-runs the full pipeline via `export_web_data.py`, refreshes
`outputs/website_data.json`, and rebuilds `outputs/index.html` from
`website_template.html` (the editable source &mdash; edit this file, never
`outputs/index.html` directly, since the latter is a generated artifact).

## Pipeline (matches the technical brief 1:1)

```
Input: Chandrayaan-2 DFSAR + OHRC  (data_simulator.py stands in for this)
   |
Stage 1: Feature Extraction           -> feature_extraction.py
   (CPR, DOP, m-chi decomposition, slope, roughness, illumination;
    triple-evidence ice mask vs. naive CPR-only baseline)
   |
Stage 2: Ice Likelihood Estimation    -> ice_estimation.py
   (Random Forest trained on Stage-1 pseudo-labels; per-pixel likelihood %
    with bootstrap confidence interval across trees)
   |
Stage 3-4: Mission Suitability & Ranking -> mission_scoring.py
   (candidate site generation + Science-First / Safety-First / Balanced
    weighted scoring + explainable trade-off notes)
   |
Stage 5: Energy-Aware Rover Path Planning -> rover_planning.py
   (NetworkX graph, cost = distance * (1 + 0.05*slope^2) * roughness,
    hard constraints on slope/illumination, battery budget tracking)
   |
Validation                             -> validation.py
   |
Output: Mission Intelligence Report    -> report.py + visualization.py
```

## Module map

| Module | Role |
|---|---|
| `selene_ai/data_simulator.py` | Synthetic DFSAR/OHRC-like scene generator (swap for real data loader) |
| `selene_ai/feature_extraction.py` | m-chi decomposition, triple-evidence detector, false-positive stats |
| `selene_ai/ice_estimation.py` | Random Forest ice likelihood + uncertainty |
| `selene_ai/mission_scoring.py` | Candidate sites, 3 mission profiles, weighted scoring, trade-off notes |
| `selene_ai/rover_planning.py` | Energy-aware graph search (Dijkstra via NetworkX) |
| `selene_ai/validation.py` | Overlap/PSR-compliance/baseline-comparison checks |
| `selene_ai/visualization.py` | Static panel (matplotlib) + interactive dashboard (Plotly) |
| `selene_ai/report.py` | Assembles the final Markdown mission report |
| `main.py` | Orchestrates the full pipeline |

## Swapping in real Chandrayaan-2 data

1. Download DFSAR + OHRC products for a target doubly-shadowed crater from
   ISSDC PRADAN.
2. Derive CPR, DOP, and m-chi decomposition powers using PolSARpro (as named
   in the technical brief) or a custom GDAL/rasterio pipeline.
3. Derive slope/roughness from a DEM (LOLA or Chandrayaan-2 TMC-derived) and
   illumination hours from an illumination model over the mission timeframe.
4. Replace the call to `simulate_crater_scene()` in `main.py` with a loader
   that returns a dict with the same keys (`cpr`, `dop`, `surface_power`,
   `volume_power`, `double_bounce_power`, `slope_deg`, `roughness`,
   `illumination_hours`, `floor_mask`, `meta`). Everything downstream is
   unchanged.

## Known limitations (also in the generated report)

- CPR anomalies are ice-*consistent*, not ice-*proven* - m-chi reduces but
  doesn't eliminate ambiguity.
- No real ground truth exists for the lunar south pole; validation here runs
  against the synthetic scene's seeded ice patch as a stand-in for published
  Mini-RF anomaly maps.
- Slope has ±3° uncertainty in a real system; should be cross-validated
  against LOLA DEM.
- The rover energy cost is *relative* (for route comparison), not an
  absolute Wh power budget.
