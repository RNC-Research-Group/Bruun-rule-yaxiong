#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 25 22:39:36 2025

@author: yshe948
"""

from tqdm import tqdm
import geopandas as gpd
import numpy as np
import rasterio as rio
import matplotlib.pyplot as plt
import os

# input shoreline points directory; choose first gpkg found
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
inputshorelinepoints = os.path.join(base_dir, "input/shorelinepoints")
bathyname = r"nzbathy_2016.tif"
preferred_file = "latestuniquepoints_merged.gpkg"
preferred_path = os.path.join(inputshorelinepoints, preferred_file)
if not os.path.exists(preferred_path):
    raise FileNotFoundError(
        f"required shoreline file not found: {preferred_file} in {inputshorelinepoints}"
    )
inputshorelinepointsfilename = preferred_file
# Birkemeier branch: B is the coastal LiDAR elevation at the shoreline point XY
# (dune toe / vegetation edge), not a buffered dune peak.

outputloc = r"output/dunepeak"
outputfilename = "shoretoe_elev_birkemeier.gpkg"
outputfigname = "shoretoe_elev_birkemeier.png"
# currentlocation
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder, outputloc), exist_ok=True)
coastfolderloc = os.path.join(grandparent_folder, "input/CoastalLiDAR")
bathyfolderloc = os.path.join(grandparent_folder, "input/Bathymetry250m")

# load shoreline point data
lastestuniquepoints = gpd.read_file(
    os.path.join(grandparent_folder, inputshorelinepoints, inputshorelinepointsfilename)
)
print("shoreline points CRS:", lastestuniquepoints.crs)

coast_DEM = os.path.join(coastfolderloc, "NewZealand_Coastal_DEM_Merged_250m.tif")

# Point-sample coastal LiDAR DEM at each shoreline XY (dune toe / veg edge)
coast_elev = np.full(len(lastestuniquepoints), np.nan)

with rio.open(coast_DEM) as src:
    if lastestuniquepoints.crs != src.crs:
        lastestuniquepoints = lastestuniquepoints.to_crs(src.crs)

    left, bottom, right, top = src.bounds

    for i, geom in tqdm(
        enumerate(lastestuniquepoints.geometry),
        total=len(lastestuniquepoints),
        desc="Sampling coastal LiDAR at shoreline points",
    ):
        if not (left <= geom.x <= right and bottom <= geom.y <= top):
            continue
        try:
            val = list(src.sample([(geom.x, geom.y)]))[0][0]
            if src.nodata is not None and val == src.nodata:
                val = np.nan
            if not np.isfinite(val) or val <= -9990 or val > 1000:
                val = np.nan
            coast_elev[i] = val
        except Exception:
            continue

lastestuniquepoints["coast_elev_m"] = coast_elev
# lastestuniquepoints["source_DEM"] = coast_source

# === Open DEM ===
bathy_path = os.path.join(bathyfolderloc, bathyname)

with rio.open(bathy_path) as src:
    # Reproject shoreline points if needed
    if lastestuniquepoints.crs != src.crs:
        lastestuniquepoints = lastestuniquepoints.to_crs(src.crs)
        print(f"Reprojected shoreline points to match DEM CRS: {src.crs}")

    # Prepare list for peak elevation values
    peak_elev_values = []

    # Loop through each shoreline point
    for geom in tqdm(
        lastestuniquepoints.geometry, desc="Sampling DEM values from bathy"
    ):
        try:
            val = list(src.sample([(geom.x, geom.y)]))[0][0]
            peak_val = val
        except Exception:
            peak_val = np.nan

        peak_elev_values.append(peak_val)

# === Add shoreline-point DEM value to GeoDataFrame ===
lastestuniquepoints["shoreline_elev_m"] = peak_elev_values


# savedata
lastestuniquepoints.to_file(
    os.path.join(grandparent_folder, outputloc, outputfilename), driver="gpkg"
)

var = "coast_elev_m"
vmin = lastestuniquepoints[var].quantile(0.02)
vmax = lastestuniquepoints[var].quantile(0.98)

fig, ax = plt.subplots(figsize=(8, 6))
im = lastestuniquepoints.plot(
    column=var,
    ax=ax,
    vmin=vmin,
    vmax=vmax,
    legend=True,
    cmap="viridis",
    markersize=40,
    edgecolor="k",
    linewidth=0.3,
)
cbar = im.get_figure().axes[-1]
cbar.set_ylabel("Height (m)", fontsize=10)
mean_var = lastestuniquepoints[var].mean()
std_var = lastestuniquepoints[var].std()
ax.set_title(
    f"Shoreline point elevation (dune toe / veg edge)\n"
    f"mean={mean_var:.1f}\xb1{std_var:.1f} m",
    fontsize=10,
)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_aspect("equal")
plt.tight_layout()
plt.show()

fig.savefig(
    os.path.join(grandparent_folder, outputloc, outputfigname),
    dpi=300,
    bbox_inches="tight",
)
