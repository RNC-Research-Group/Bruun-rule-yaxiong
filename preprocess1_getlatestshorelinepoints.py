#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 23 09:43:54 2025

@author: yshe948
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

# output
outputloc = r"input/shorelinepoints"

# locate folder
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder, outputloc), exist_ok=True)

# input
crsused = 2193
input_csv = os.path.join(os.path.dirname(current_script), "slpoints_rates.csv")

required_cols = [
    "Distance",
    "IntersectX",
    "IntersectY",
    "Unique_ID",
    "Date",
    "NSM",
    "WLR",
    "Region",
    "Start_date",
    "End_date",
    "Duration",
]

points = pd.read_csv(input_csv, low_memory=False)
missing_cols = [col for col in required_cols if col not in points.columns]
if missing_cols:
    raise KeyError(f"missing required columns in {input_csv}: {missing_cols}")

# Keep only fields required for downstream matching and requested exports.
points = points[required_cols].copy()
points["Distance"] = pd.to_numeric(points["Distance"], errors="coerce")
points["IntersectX"] = pd.to_numeric(points["IntersectX"], errors="coerce")
points["IntersectY"] = pd.to_numeric(points["IntersectY"], errors="coerce")
points["WLR"] = pd.to_numeric(points["WLR"], errors="coerce")
points["Date_dt"] = pd.to_datetime(points["Date"], dayfirst=True, errors="coerce")

# Remove rows that cannot be placed or grouped reliably.
points = points.dropna(subset=["Unique_ID", "IntersectX", "IntersectY", "Date_dt"])

# Remove rows with missing/zero retreat rate so unmatched join-fill rows are excluded.
points = points[points["WLR"].notna() & (points["WLR"] != 0)].copy()

# Preserve full per-transect history for orientation vectors before selecting latest rows.
points_for_vectors = points.copy()

outputfile_path_points_gpkg = os.path.join(
    grandparent_folder, outputloc, "latestuniquepoints_merged.gpkg"
)
outputfile_path_points_shp = os.path.join(
    grandparent_folder, outputloc, "latestuniquepoints_merged.shp"
)


def calc_transect_unit_vector(group):
    group_valid = group.dropna(subset=["Distance", "IntersectX", "IntersectY"])
    if group_valid.empty:
        return pd.Series({"ux1": np.nan, "uy1": np.nan})

    seaward = group_valid.loc[group_valid["Distance"].idxmin()]
    landward = group_valid.loc[group_valid["Distance"].idxmax()]

    dx_line1 = -seaward["IntersectX"] + landward["IntersectX"]
    dy_line1 = -seaward["IntersectY"] + landward["IntersectY"]
    length1 = np.hypot(dx_line1, dy_line1)

    if length1 == 0:
        return pd.Series({"ux1": np.nan, "uy1": np.nan})

    return pd.Series({"ux1": dx_line1 / length1, "uy1": dy_line1 / length1})


# Keep latest point per transect by Date (no distance-based tie-break).
points = points.drop_duplicates(
    subset=[c for c in points.columns if c != "Date_dt"]
)
points = points.sort_values(["Unique_ID", "Date_dt"], ascending=[True, False])
points = points.drop_duplicates(subset=["Unique_ID"], keep="first")
lastestuniquepoints = points.copy()

# Add transect direction vectors from full transect history.
transect_vectors = points_for_vectors.groupby("Unique_ID", group_keys=False).apply(
    calc_transect_unit_vector
)
lastestuniquepoints = lastestuniquepoints.merge(
    transect_vectors.reset_index(), on="Unique_ID", how="left"
)

lastestuniquepoints = gpd.GeoDataFrame(
    lastestuniquepoints,
    geometry=gpd.points_from_xy(
        lastestuniquepoints["IntersectX"], lastestuniquepoints["IntersectY"]
    ),
    crs=f"EPSG:{crsused}",
)
lastestuniquepoints["point_X"] = lastestuniquepoints.geometry.x
lastestuniquepoints["point_Y"] = lastestuniquepoints.geometry.y

# Preserve requested fields and required geometry/vector fields.
keep_cols = [
    "Distance",
    "IntersectX",
    "IntersectY",
    "Unique_ID",
    "Date",
    "NSM",
    "WLR",
    "Region",
    "Start_date",
    "End_date",
    "Duration",
    "ux1",
    "uy1",
    "point_X",
    "point_Y",
    "geometry",
]
lastestuniquepoints = lastestuniquepoints[keep_cols].copy()

## save data
lastestuniquepoints.to_file(outputfile_path_points_gpkg, driver="GPKG")

lastestuniquepoints["Unique_ID"] = lastestuniquepoints["Unique_ID"].apply(
    lambda x: str(int(x)) if pd.notna(x) else ""
)

lastestuniquepoints.to_file(outputfile_path_points_shp, driver="ESRI Shapefile")

## figure
fig1, ax1 = plt.subplots(figsize=(100, 100))
plt.scatter(
    lastestuniquepoints["IntersectX"],
    lastestuniquepoints["IntersectY"],
    c="red",
    s=1,
    alpha=0.7,
    edgecolors="red",
    label="Points",
)
ax1.set_aspect("equal")

fig1.savefig(
    os.path.join(
        grandparent_folder, outputloc, "latestuniquepoints_merged.png"
    ),
    dpi=300,
    bbox_inches="tight",
)
plt.close(fig1)
