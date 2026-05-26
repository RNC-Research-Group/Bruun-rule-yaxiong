#!/usr/bin/env python3
"""
Run the full Bruun-rule pipeline for all three depth-of-closure equations:
  hallermeier_inner  (hallin)  — B from MHWS berm elevation
  hallermeier_outer  (hallout) — B from dune-crest profile elevation + D50
  birkemeier_1985    (birk)    — B from MHWS berm elevation

For each equation the following steps are executed:
  step2  → wave summary + CD per wave gauge
  step3  → match wave gauges to shoreline transects
  step4  → Bruun rule recession per transect
  step5  → add SLR scenarios (all years / SSPs / confidence bands)

Output CSV naming:
  NZ_{confidence}_y{year}_s{scenario}_p{percentile}_{suffix}.csv
  e.g. NZ_medium_confidence_y2100_s4.5_p0.5_hallin.csv

Prerequisites (run once before this script):
  preprocess1_getlatestshorelinepoints.py
  preprocess2_dunepeak.py          → output/dunepeak/shoretoe_elev_combined.gpkg
  preprocess2_SLRscenario.py       → input/SLR/ scenario GPKGs
  preprocess2_matchSLRandshorelinepoints.py
  step1_expandpolygonandfilterwavegauge.py
"""
import os
import subprocess
import sys

PYTHON = sys.executable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

EQUATIONS = [
    "hallermeier_inner",
    "hallermeier_outer",
    "birkemeier_1985",
]

STEPS = [
    "step2_H12handT12h.py",
    "step3_matchwgandshorelinepoints.py",
    "step4_bruunrule.py",
    "step5_addSLR.py",
]


def run_step(script: str, eq: str) -> None:
    env = {**os.environ, "CD_METHOD": eq}
    script_path = os.path.join(SCRIPT_DIR, script)
    print(f"\n{'='*60}")
    print(f"  {eq} | {script}")
    print(f"{'='*60}")
    result = subprocess.run(
        [PYTHON, script_path],
        env=env,
        cwd=SCRIPT_DIR,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"FAILED: {script} for equation={eq} (exit code {result.returncode})"
        )


def main() -> None:
    print(f"Running all equations: {EQUATIONS}")
    for eq in EQUATIONS:
        for step in STEPS:
            run_step(step, eq)
    print("\nAll equations completed successfully.")


if __name__ == "__main__":
    main()
