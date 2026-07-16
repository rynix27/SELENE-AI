# SELENE-AI - Mission Intelligence Report
*Generated 2026-07-14 12:34 | Scene: Simulated PSR crater (Faustini-type doubly shadowed crater)*
*Data source: SYNTHETIC -- stand-in for Chandrayaan-2 DFSAR + OHRC (ISSDC PRADAN)*

## 1. Ice Detection Summary
- CPR-only (naive) detection footprint: **826 px**
- Triple-evidence (CPR + m-chi + PSR) detection footprint: **80 px**
- False-positive area reduction: **90.3%**
- Rough-terrain false positives removed: **643 px**

## 2. Ranked Landing Sites by Mission Profile

### Profile: Science First
| Rank | Site | Score | Ice % | Slope° | Solar h | Dist. to ice (m) | Trade-off |
|---|---|---|---|---|---|---|---|
| 1 | Site-A | 88.4 | 10.6 | 6.8 | 4.3 | 72.1 | highest ice-proximity score in shortlist (10.6%); shortest rover traverse required in shortlist (72 m) |
| 2 | Site-B | 81.2 | 9.5 | 6.5 | 4.2 | 89.4 | gentlest slope (safest) in shortlist (6.5 deg) |
| 3 | Site-C | 38.3 | 6.7 | 7.3 | 4.4 | 107.7 | steepest slope (least safe) in shortlist (7.3 deg) |
| 4 | Site-D | 32.9 | 3.8 | 7.2 | 4.6 | 89.4 | most solar power available in shortlist (4.6 h/day) |
| 5 | Site-E | 30.5 | 4.6 | 7.1 | 4.1 | 102.0 | tightest solar power budget in shortlist (4.1 h/day) |
| 6 | Site-F | 13.9 | 2.8 | 7.2 | 4.2 | 141.4 | lowest ice-proximity score in shortlist (2.8%); longest rover traverse required in shortlist (141 m) |

### Profile: Safety First
| Rank | Site | Score | Ice % | Slope° | Solar h | Dist. to ice (m) | Trade-off |
|---|---|---|---|---|---|---|---|
| 1 | Site-B | 72.6 | 9.5 | 6.5 | 4.2 | 89.4 | gentlest slope (safest) in shortlist (6.5 deg) |
| 2 | Site-A | 68.9 | 10.6 | 6.8 | 4.3 | 72.1 | highest ice-proximity score in shortlist (10.6%); shortest rover traverse required in shortlist (72 m) |
| 3 | Site-D | 45.0 | 3.8 | 7.2 | 4.6 | 89.4 | most solar power available in shortlist (4.6 h/day) |
| 4 | Site-C | 27.9 | 6.7 | 7.3 | 4.4 | 107.7 | steepest slope (least safe) in shortlist (7.3 deg) |
| 5 | Site-F | 25.4 | 2.8 | 7.2 | 4.2 | 141.4 | lowest ice-proximity score in shortlist (2.8%); longest rover traverse required in shortlist (141 m) |
| 6 | Site-E | 25.1 | 4.6 | 7.1 | 4.1 | 102.0 | tightest solar power budget in shortlist (4.1 h/day) |

### Profile: Balanced
| Rank | Site | Score | Ice % | Slope° | Solar h | Dist. to ice (m) | Trade-off |
|---|---|---|---|---|---|---|---|
| 1 | Site-A | 78.6 | 10.6 | 6.8 | 4.3 | 72.1 | highest ice-proximity score in shortlist (10.6%); shortest rover traverse required in shortlist (72 m) |
| 2 | Site-B | 76.6 | 9.5 | 6.5 | 4.2 | 89.4 | gentlest slope (safest) in shortlist (6.5 deg) |
| 3 | Site-D | 38.4 | 3.8 | 7.2 | 4.6 | 89.4 | most solar power available in shortlist (4.6 h/day) |
| 4 | Site-C | 34.4 | 6.7 | 7.3 | 4.4 | 107.7 | steepest slope (least safe) in shortlist (7.3 deg) |
| 5 | Site-E | 26.7 | 4.6 | 7.1 | 4.1 | 102.0 | tightest solar power budget in shortlist (4.1 h/day) |
| 6 | Site-F | 17.1 | 2.8 | 7.2 | 4.2 | 141.4 | lowest ice-proximity score in shortlist (2.8%); longest rover traverse required in shortlist (141 m) |

## 3. Rover Traverse Plan
- Feasible path found: **14 segments**
- Total distance: **354.6 m**
- Total relative energy cost: **166.04**
- Max consecutive dark (battery-only) steps: **13** (within battery budget)

## 4. Validation Results
| Check | Result | Target | Passed |
|---|---|---|---|
| Spatial overlap with reference ice zone | 50.6% | >70% spatial overlap | FAIL |
| | *Stand-in for Chandrayaan-1 Mini-RF anomaly comparison (real run: compare vs. published Mini-RF CPR anomaly maps)* | | |
| PSR compliance of detected ice pixels | 100.0% | 100% within confirmed PSRs | PASS |
| | *Real run: verify against LOLA-derived PSR boundary polygons* | | |
| False-positive area reduction vs. CPR-only baseline | 90.3% | Reduction in false-positive area (higher is better) | PASS |
| | *Triple-evidence (CPR + m-chi + PSR) vs. naive CPR > 1.0 thresholding* | | |
| Literature match vs. known priority craters | N/A (manual step) | 2+ of top 3 match named priority craters | N/A |
| | *Real run: compare top-ranked sites vs. Haworth, Shackleton, Faustini priority list* | | |

## 5. Honest Limitations
- CPR anomalies are ice-consistent, not ice-proven; m-chi decomposition reduces but does not eliminate ambiguity.
- No ground truth exists for the real lunar south pole; this prototype run uses a **synthetic scene** as a stand-in for Chandrayaan-2 DFSAR/OHRC products (swap in real ISSDC data via `data_simulator.load_real_dfsar()`).
- Slope estimates carry ±3° uncertainty in the real system; should be cross-validated with LOLA DEM.
- The rover energy model is relative (for route comparison), not an absolute power budget in Wh.

---
*SELENE-AI: Mission Intelligence from Chandrayaan-2 Data*