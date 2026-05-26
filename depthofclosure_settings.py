#!/usr/bin/env python3
import os

# Shared depth-of-closure settings for step2_H12handT12h.py.
#
# Available methods:
# - hallermeier_inner: CD = 2.28*Hs - 68.5*Hs^2/(g*T^2)
# - birkemeier_1985:   CD = 1.75*Hs - 57.9*Hs^2/(g*T^2)
# - hallermeier_outer: CD = (Hs_mean - 0.3*Hs_std)*Ts_mean*sqrt(g/(5000*d50))
#
# Set CD_METHOD below, or override at runtime by setting the CD_METHOD env var
# (used by run_all_equations.py to iterate over all three methods).
CD_METHOD = os.environ.get("CD_METHOD", "hallermeier_inner")

# Gravity constant used in the CD equations.
GRAVITY = 9.81

# Median grain size (m) for Hallermeier outer equation.
# Typical medium sand is around 0.0002 m.
D50_M = 0.0002

# Source used for B (dune/berm height) in the Bruun rule:
# - 'mhws_parquet': MHWS shoreline point elevation from nzccd_rates_proxy.parquet
#                  (appropriate for hallermeier_outer and birkemeier_1985)
# - 'dune_crest_dem': buffered maximum LiDAR DEM elevation landward of shoreline
#                    (appropriate for hallermeier_inner)
# This is set automatically based on CD_METHOD, but can be overridden here.
B_SOURCE_OVERRIDE = None  # set to 'mhws_parquet' or 'dune_crest_dem' to force

# Resolved B source: use override if set, otherwise derive from CD method.
# hallermeier_inner  → berm elevation at MHWS XY (from rates proxy parquet)
# hallermeier_outer  → dune crest elevation from landward profile (1 m DEM)
# birkemeier_1985    → berm elevation at MHWS XY (from rates proxy parquet)
_B_SOURCE_DEFAULT = {
    "hallermeier_inner": "mhws_parquet",
    "hallermeier_outer": "dune_crest_dem",
    "birkemeier_1985": "mhws_parquet",
}
B_SOURCE = B_SOURCE_OVERRIDE or _B_SOURCE_DEFAULT.get(CD_METHOD, "mhws_parquet")

# Short suffix used in output filenames to identify the equation.
CD_METHOD_SUFFIX = {
    "hallermeier_inner": "hallin",
    "hallermeier_outer": "hallout",
    "birkemeier_1985": "birk",
}
CD_METHOD_COEFFICIENTS = {
    "hallermeier_inner": {"a": 2.28, "b": 68.5},
    "birkemeier_1985": {"a": 1.75, "b": 57.9},
    "hallermeier_outer": None,
}
