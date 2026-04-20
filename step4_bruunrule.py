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
import glob
from pyproj import Transformer
from tqdm.auto import tqdm

tqdm.pandas()
from tqdm.contrib.concurrent import process_map

# input
inputloctransect = r"output/match"
transect_wp_gpkg = "transect_wp.gpkg"
inputlocdunepeak = r"output/dunepeak"
# Match the dunepeak parameters from preprocess2_dunepeak.py: fw5_bw20_s5_pct5
# If multiple pct versions exist, prefer pct5 (most recent standard)
dunepeak_gpkg = "dunepeak_pct5_fw5_bw20_s5.gpkg"
bathyfolderloc = r"input/Bathymetry250m"
bathyname = r"nzbathy_2016.tif"


outputfigurefolder = "output/transect"
outputfolder = r"output/bruunrule"
outputfilename_gpkg = "bruunrule.gpkg"
outputfilename_shp = "bruunrule.shp"

# DSAS rates source for total observed retreat used in Bruun retreat term.
# This CSV must contain Unique_ID, WLR and Duration.
with_rates_csv_pattern = "*_with_rates.csv"


maxdunepeak = 10
extend_landward_m = 200  # meters to extend beyond start
extend_seaward_m = 2000  # meters to extend beyond end
extend_seaward_m_fallback = 25000  # retry farther offshore only if no CD crossing is found
dx_bathy = 250
S = 1
buffer_plotbathydem = 10000  # metres or coordinate units
# dx_coast=1
# current folder
current_script = os.path.abspath(__file__)
script_folder = os.path.dirname(current_script)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder, outputfigurefolder), exist_ok=True)
os.makedirs(os.path.join(grandparent_folder, outputfolder), exist_ok=True)

bathy_path = os.path.join(grandparent_folder, bathyfolderloc, bathyname)

# load data
transect_wp = gpd.read_file(
    os.path.join(grandparent_folder, inputloctransect, transect_wp_gpkg)
)

# Load rates from *_with_rates.csv and merge onto transects by Unique_ID.
rate_candidates = sorted(glob.glob(os.path.join(script_folder, with_rates_csv_pattern)))
if not rate_candidates:
    raise FileNotFoundError(
        f"no with-rates CSV found in {script_folder} matching {with_rates_csv_pattern}"
    )

rates_csv_path = rate_candidates[0]
rates_df = pd.read_csv(rates_csv_path)

required_rate_cols = ["WLR", "Duration"]
missing_rate_cols = [col for col in required_rate_cols if col not in rates_df.columns]
if missing_rate_cols:
    raise KeyError(
        f"missing required columns in {os.path.basename(rates_csv_path)}: {missing_rate_cols}"
    )

id_col_candidates = ["Unique_ID", "UniqueID"]
rate_id_col = next((col for col in id_col_candidates if col in rates_df.columns), None)
if rate_id_col is None:
    raise KeyError(
        f"missing ID column in {os.path.basename(rates_csv_path)}; expected one of {id_col_candidates}"
    )

transect_wp["Unique_ID_norm"] = (
    pd.to_numeric(transect_wp["Unique_ID"], errors="coerce").astype("Int64").astype(str)
)
rates_df["Unique_ID_norm"] = (
    pd.to_numeric(rates_df[rate_id_col], errors="coerce").astype("Int64").astype(str)
)

rate_merge_cols = ["Unique_ID_norm", "WLR", "Duration"]
for optional_col in ["Start_date", "End_date"]:
    if optional_col in rates_df.columns:
        rate_merge_cols.append(optional_col)

rates_df = rates_df[rate_merge_cols].drop_duplicates(subset=["Unique_ID_norm"]).copy()

# Always source these fields from with-rates CSV.
transect_wp = transect_wp.drop(
    columns=["WLR", "Duration", "Start_date", "End_date"], errors="ignore"
)
transect_wp = transect_wp.merge(rates_df, on="Unique_ID_norm", how="left")
transect_wp["WLR"] = pd.to_numeric(transect_wp["WLR"], errors="coerce")
transect_wp["Duration"] = pd.to_numeric(transect_wp["Duration"], errors="coerce")
transect_wp["historic_retreat_obs_m"] = transect_wp["WLR"] * transect_wp["Duration"]

matched_with_rates = int(transect_wp["historic_retreat_obs_m"].notna().sum())
print(
    f"rates source: {rates_csv_path}; matched observed-retreat rows: "
    f"{matched_with_rates}/{len(transect_wp)}"
)

dunepeak_all = gpd.read_file(
    os.path.join(grandparent_folder, inputlocdunepeak, dunepeak_gpkg)
)
dem_bathy = rio.open(bathy_path)

# Ensure transect point vectors are in the same CRS as bathymetry sampling.
if transect_wp.crs is not None and transect_wp.crs != dem_bathy.crs:
    transformer = Transformer.from_crs(transect_wp.crs, dem_bathy.crs, always_xy=True)
    transect_wp["point_X"], transect_wp["point_Y"] = transformer.transform(
        transect_wp["point_X"].values, transect_wp["point_Y"].values
    )
    if "wave_X" in transect_wp.columns and "wave_Y" in transect_wp.columns:
        transect_wp["wave_X"], transect_wp["wave_Y"] = transformer.transform(
            transect_wp["wave_X"].values, transect_wp["wave_Y"].values
        )
    transect_wp = transect_wp.to_crs(dem_bathy.crs)

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

    def find_intersection_distances(search_extend_seaward_m):
        distances_bathy = np.arange(
            -extend_landward_m, length + search_extend_seaward_m + dx_bathy, dx_bathy
        )

        x_vals_bathy = x0 + ux * distances_bathy
        y_vals_bathy = y0 + uy * distances_bathy

        xmin, ymin, xmax, ymax = dem_bathy.bounds
        mask1_bathy = (
            (x_vals_bathy >= xmin)
            & (x_vals_bathy <= xmax)
            & (y_vals_bathy >= ymin)
            & (y_vals_bathy <= ymax)
        )

        x_vals_bathy = x_vals_bathy[mask1_bathy]
        y_vals_bathy = y_vals_bathy[mask1_bathy]
        distances_bathy_clipped = distances_bathy[mask1_bathy]

        coords_bathy = list(zip(x_vals_bathy, y_vals_bathy))
        if not coords_bathy:
            return [], np.array([]), np.array([])

        dem_bathy_profile = np.array(
            [val[0] for val in dem_bathy.sample(coords_bathy)], dtype=float
        )

        mask2_bathy = (distances_bathy_clipped >= 0) & (
            distances_bathy_clipped <= length + search_extend_seaward_m
        )

        dist_segment_bathy = distances_bathy_clipped[mask2_bathy]
        dem_segment_bathy = dem_bathy_profile[mask2_bathy]

        crossings = np.where(np.diff(np.sign(dem_segment_bathy - target_z)))[0]
        intersection_distances_local = []

        for idx in crossings:
            z1, z2 = dem_segment_bathy[idx], dem_segment_bathy[idx + 1]
            dist1, dist2 = dist_segment_bathy[idx], dist_segment_bathy[idx + 1]

            if z2 != z1:  # avoid division by zero
                dist_cross = dist1 + (target_z - z1) * (dist2 - dist1) / (z2 - z1)
                intersection_distances_local.append(dist_cross)

        return intersection_distances_local, dist_segment_bathy, dem_segment_bathy

    ## find location of CD and dune peak
    target_z = -row.CD
    intersection_distances, dist_segment_bathy, dem_segment_bathy = (
        find_intersection_distances(extend_seaward_m)
    )
    row["closure_search_extension_m"] = extend_seaward_m

    if not intersection_distances and extend_seaward_m_fallback > extend_seaward_m:
        (
            intersection_distances,
            dist_segment_bathy,
            dem_segment_bathy,
        ) = find_intersection_distances(extend_seaward_m_fallback)
        if intersection_distances:
            row["closure_search_extension_m"] = extend_seaward_m_fallback

    # find the dune peak one
    uniqueID_transect = row["Unique_ID"]
    match = dunepeak_all[dunepeak_all["Unique_ID"] == uniqueID_transect]

    row["target_z"] = target_z
    row["n_crossings"] = len(intersection_distances)
    row["closure_dist_min"] = np.nan
    row["closure_dist_max"] = np.nan
    row["closure_dist_median"] = np.nan
    row["closure_found"] = False

    coast_elev = match.iloc[0]["coast_elev_m"]
    shoreline_elev = match.iloc[0]["shoreline_elev_m"]

    if pd.notna(coast_elev) and coast_elev < maxdunepeak:
        dunepeak = coast_elev
        row["choosefrom"] = "coast"
    elif shoreline_elev < maxdunepeak:
        dunepeak = shoreline_elev
        row["choosefrom"] = "shoreline"
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
        row["closure_dist_min"] = float(np.min(intersection_distances))
        row["closure_dist_max"] = float(np.max(intersection_distances))
        row["closure_dist_median"] = float(intersection_median)
        row["closure_found"] = True
        # print("Intersection at median distance along transect:", intersection_median)
        row["L"] = (
            intersection_median  # horizontal distance between closure depth and dune peak
        )

        # Bruun retreat component (geometry-driven)
        row["R_bruun"] = S * intersection_median / (dunepeak - target_z)

        # Historic retreat component from with-rates CSV:
        # total observed retreat over the observation period = WLR * Duration.
        # If rates are unavailable for a transect, default to 0 to preserve base Bruun behavior.
        historic_retreat_obs_m = (
            row["historic_retreat_obs_m"]
            if ("historic_retreat_obs_m" in row and pd.notna(row["historic_retreat_obs_m"]))
            else 0.0
        )
        row["historic_retreat_obs_m"] = historic_retreat_obs_m

        # Combined retreat metric for current workflow:
        # add observed historical retreat term to Bruun retreat term.
        row["R"] = row["R_bruun"] + historic_retreat_obs_m
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
        row["R_bruun"] = np.nan
        # Keep observed retreat term from CSV even when closure cannot be resolved.
        row["historic_retreat_obs_m"] = (
            row["historic_retreat_obs_m"]
            if ("historic_retreat_obs_m" in row and pd.notna(row["historic_retreat_obs_m"]))
            else np.nan
        )
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
savetransect_wp = savetransect_wp.drop(columns=["Unique_ID_norm"], errors="ignore")
if savetransect_wp.crs is None:
    savetransect_wp.set_crs(dem_bathy.crs, inplace=True)
elif savetransect_wp.crs != dem_bathy.crs:
    savetransect_wp = savetransect_wp.to_crs(dem_bathy.crs)

savetransect_wp.to_file(
    os.path.join(grandparent_folder, outputfolder, outputfilename_gpkg), driver="GPKG"
)
savetransect_wp.to_file(
    os.path.join(grandparent_folder, outputfolder, outputfilename_shp),
    driver="ESRI Shapefile",
)
