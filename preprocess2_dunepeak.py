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
from rasterio.mask import mask
import matplotlib.pyplot as plt
import os
import math

inputshorelinepoints = r"input\shorelinepoints"
shorelinepointfilename = "Wa"  # JaMoNoRaSoWa
inputshorelinepointsfilename = f"lastestuniquepoints_{shorelinepointfilename}.gpkg"
coastfolderloc = r"Z:\CoastalLiDAR"
bathyfolderloc = r"Z:\Bathymetry250m"
bathyname = r"nzbathy_2016.tif"
buffer_dist = 5  # unit m
outputloc = r"output\dunepeak"
outputfilename = f"{shorelinepointfilename}_dunepeak_{buffer_dist}.gpkg"
outputfigname = f"{shorelinepointfilename}_dunepeak_{buffer_dist}.png"
# currentlocation
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder, outputloc), exist_ok=True)

# load shoreline point data
lastestuniquepoints = gpd.read_file(
    os.path.join(grandparent_folder, inputshorelinepoints, inputshorelinepointsfilename)
)
print("shoreline points CRS:", lastestuniquepoints.crs)


matched_files = []
for root, dirs, files in os.walk(coastfolderloc):
    for file in files:
        if file.endswith(".tif") and "NewZealand" in file:
            matched_files.append(os.path.join(root, file))


coast_elev = np.full(len(lastestuniquepoints), np.nan)  # initialise all NaN
# coast_source = np.full(len(lastestuniquepoints), None, dtype=object)

for f in matched_files:
    with rio.open(f) as src:
        # Reproject buffer to DEM CRS if needed

        if lastestuniquepoints.crs != src.crs:
            lastestuniquepoints = lastestuniquepoints.to_crs(src.crs)

        left, bottom, right, top = src.bounds

        # Loop through points that are still NaN
        for i, geom in tqdm(
            enumerate(lastestuniquepoints.geometry),
            total=len(lastestuniquepoints),
            desc="Processing points",
        ):
            # Skip if already found a value
            if not np.isnan(coast_elev[i]):
                continue

            # Skip if point outside DEM extent
            if not (left <= geom.x <= right and bottom <= geom.y <= top):
                continue

            # Try sampling from this DEM
            try:
                if buffer_dist > 0:
                    # Create buffer polygon
                    geom_buffer = geom.buffer(buffer_dist)
                    # Crop DEM within buffer polygon
                    out_image, _ = mask(src, [geom_buffer], crop=True)
                    out_image[out_image > 1000] = -9999
                    # Peak elevation (maximum value inside buffer)
                    val = np.nanmax(out_image)
                else:
                    val = list(src.sample([(geom.x, geom.y)]))[0][0]
                    if val > 1000:
                        val = math.nan
                if not np.isnan(val):
                    coast_elev[i] = val  # assign to correct row
                    # coast_source[i] = f  # record DEM file path
            except Exception:
                continue  # skip invalid or out-of-bounds sample

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

# === Add DEM value to GeoDataFrame ===
lastestuniquepoints["bathy_elev_m"] = peak_elev_values


# savedata
lastestuniquepoints.to_file(
    os.path.join(grandparent_folder, outputloc, outputfilename), driver="gpkg"
)

var = "coast_elev_m"
# Cap values greater than 10
lastestuniquepoints[var] = lastestuniquepoints[var].clip(lower=0, upper=10)

fig, ax = plt.subplots(figsize=(8, 6))
im = lastestuniquepoints.plot(
    column=var,
    ax=ax,
    legend=True,
    cmap="viridis",
    markersize=40,
    edgecolor="k",
    linewidth=0.3,
)
cbar = im.get_figure().axes[-1]  # colourbar axis is the last axis
cbar.set_ylabel("Height (m)", fontsize=10)
mean_var = lastestuniquepoints[var].mean()
std_var = lastestuniquepoints[var].std()
ax.set_title(
    f"{shorelinepointfilename}: \n buffer={buffer_dist} m \n dunepeak={mean_var:.1f}±{std_var:.1f} m",
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
