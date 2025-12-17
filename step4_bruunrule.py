#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Oct 26 10:51:48 2025

@author: yshe948
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import rasterio as rio
import os
import math
from tqdm.auto import tqdm

tqdm.pandas()
from tqdm.contrib.concurrent import process_map

# input
shorelinepointfilename = "JaMoNoRaSoWa"  # JaMoNoRaSoWa
inputloctransect = r"output/match"
transect_wp_gpkg = f"transect_wp_{shorelinepointfilename}.gpkg"
inputlocdunepeak = r"output/dunepeak"
buffer_dist = 5
dunepeak_gpkg = f"{shorelinepointfilename}_dunepeak_{buffer_dist}.gpkg"
bathyfolderloc = r"input/Bathymetry250m"
bathyname = r"nzbathy_2016.tif"


outputfigurefolder = f"output/transect_{shorelinepointfilename}_buffer_{buffer_dist}"
outputfolder = r"output/brunnrule"
outputfilename_gpkg = f"brunnrule_{shorelinepointfilename}_buffer_{buffer_dist}.gpkg"
outputfilename_shp = f"brunnrule_{shorelinepointfilename}_buffer_{buffer_dist}.shp"


maxdunepeak = 10
extend_landward_m = 200  # meters to extend beyond start
extend_seaward_m = 2000  # meters to extend beyond end
dx_bathy = 250
S = 1
buffer_plotbathydem = 10000  # metres or coordinate units
# dx_coast=1
# current folder
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder, outputfigurefolder), exist_ok=True)
os.makedirs(os.path.join(grandparent_folder, outputfolder), exist_ok=True)

bathy_path = os.path.join(grandparent_folder, bathyfolderloc, bathyname)

# load data
transect_wp = gpd.read_file(
    os.path.join(grandparent_folder, inputloctransect, transect_wp_gpkg)
)
dunepeak_all = gpd.read_file(
    os.path.join(grandparent_folder, inputlocdunepeak, dunepeak_gpkg)
)
dem_bathy = rio.open(bathy_path)

print(
    os.path.join(grandparent_folder, inputloctransect, transect_wp_gpkg),
    transect_wp.crs,
)
print(
    os.path.join(grandparent_folder, inputlocdunepeak, dunepeak_gpkg), dunepeak_all.crs
)
print(bathy_path, dem_bathy.crs)

n_transect_wp = len(transect_wp)
num_digits = math.ceil(
    math.log10(n_transect_wp + 1)
)  # +1 in case n is exactly a power of 10
# Suppose transect_wp is your dataframe


# Number of digits for zero-padding
num_digits = math.ceil(
    math.log10(n_transect_wp + 1)
)  # +1 in case n is exactly a power of 10


def process_row(tup):
    if type(tup) is tuple:
        _, row = tup
    else:
        row = tup
    # row = row.to_dict()
    x0, y0 = row["point_X"], row["point_Y"]
    x1, y1 = row["wave_X"], row["wave_Y"]

    # Transect length
    dx_line = x1 - x0
    dy_line = y1 - y0
    length = np.hypot(dx_line, dy_line)

    # Unit vector in the transect direction
    ux, uy = dx_line / length, dy_line / length

    # Extended distances along the transect (includes extra before and after)
    distances_bathy = np.arange(
        -extend_landward_m, length + extend_seaward_m + dx_bathy, dx_bathy
    )

    # Coordinates along the extended transect
    x_vals_bathy = x0 + ux * distances_bathy
    y_vals_bathy = y0 + uy * distances_bathy

    xmin, ymin, xmax, ymax = dem_bathy.bounds
    # Create mask for points inside DEM bounds
    mask1_bathy = (
        (x_vals_bathy >= xmin)
        & (x_vals_bathy <= xmax)
        & (y_vals_bathy >= ymin)
        & (y_vals_bathy <= ymax)
    )

    x_vals_bathy = x_vals_bathy[mask1_bathy]
    y_vals_bathy = y_vals_bathy[mask1_bathy]
    distances_bathy_clipped = distances_bathy[mask1_bathy]

    # DEM sample
    coords_bathy = list(zip(x_vals_bathy, y_vals_bathy))

    dem_bathy_profile = [val[0] for val in dem_bathy.sample(coords_bathy)]

    mask2_bathy = (distances_bathy_clipped >= 0) & (
        distances_bathy_clipped <= length + extend_seaward_m
    )

    dist_segment_bathy = distances_bathy_clipped[mask2_bathy]
    dem_segment_bathy = np.array(dem_bathy_profile)[mask2_bathy]

    ## find location of CD and dune peak
    target_z = -row.CD
    crossings = np.where(np.diff(np.sign(dem_segment_bathy - target_z)))[0]

    intersection_distances = []

    for idx in crossings:
        z1, z2 = dem_segment_bathy[idx], dem_segment_bathy[idx + 1]
        dist1, dist2 = dist_segment_bathy[idx], dist_segment_bathy[idx + 1]

        if z2 != z1:  # avoid division by zero
            dist_cross = dist1 + (target_z - z1) * (dist2 - dist1) / (z2 - z1)
            intersection_distances.append(dist_cross)

    # find the dune peak one
    uniqueID_transect = row["Unique_ID"]
    match = dunepeak_all[dunepeak_all["Unique_ID"] == uniqueID_transect]

    coast_elev = match.iloc[0]["coast_elev_m"]
    bathy_elev = match.iloc[0]["bathy_elev_m"]

    if pd.notna(coast_elev) and coast_elev < maxdunepeak:
        dunepeak = coast_elev
        row["choosefrom"] = "coast"
    elif bathy_elev < maxdunepeak:
        dunepeak = bathy_elev
        row["choosefrom"] = "bathy"
    else:
        dunepeak = maxdunepeak
        row["choosefrom"] = "max"

    if dunepeak < 0:
        dunepeak = 0
        row["choosefrom"] = "0"

    # # find the SLR
    # match_SLR = SLR_match[SLR_match["Unique_ID"] == uniqueID_transect]
    # SLR_siteID=match_SLR["Site ID"].iloc[0]
    # match_SLR_senario=SLR_scenario[SLR_scenario["Site ID"]==SLR_siteID]

    row["B"] = dunepeak
    # row["S"]=match_SLR_senario[f"{percentile}"].iloc[0] # sea level rise
    row["S"] = 1

    if intersection_distances:
        intersection_median = np.median(intersection_distances)
        # print("Intersection at median distance along transect:", intersection_median)
        row["L"] = (
            intersection_median  # horizontal distance between closure depth and dune peak
        )
        row["R"] = (
            S * intersection_median / (dunepeak - target_z)
        )  # shoreline recession (m)
        row["tanbeta"] = (dunepeak - target_z) / intersection_median
        row["beta_rad"] = math.atan(row["tanbeta"])
        row["beta_degree"] = math.degrees(row["beta_rad"])
        # row["ER"]=row["R"]/(year-currentyear)
        newx_profile = -row["R"]  # landward from dune peak
        x_new = x0 + row["ux1"] * newx_profile
        y_new = y0 + row["uy1"] * newx_profile

        row["x_new"] = x_new
        row["y_new"] = y_new
    else:
        intersection_median = None
        row["L"] = np.nan
        row["R"] = np.nan
        row["tanbeta"] = np.nan
        row["beta_rad"] = np.nan
        row["beta_degree"] = np.nan
        # row["ER"]=np.nan
        row["x_new"] = np.nan
        row["y_new"] = np.nan
    return row


# savetransect_wp = pd.concat(process_map(process_row, transect_wp.iterrows(), total=n_transect_wp, chunksize=10), ignore_index=True)
savetransect_wp = transect_wp.progress_apply(process_row, axis=1)

savetransect_wp["Unique_ID"] = savetransect_wp["Unique_ID"].apply(
    lambda x: str(int(x)) if pd.notna(x) else ""
)
savetransect_wp.set_crs(dem_bathy.crs, inplace=True)

savetransect_wp.to_file(
    os.path.join(grandparent_folder, outputfolder, outputfilename_gpkg), driver="GPKG"
)
savetransect_wp.to_file(
    os.path.join(grandparent_folder, outputfolder, outputfilename_shp),
    driver="ESRI Shapefile",
)
