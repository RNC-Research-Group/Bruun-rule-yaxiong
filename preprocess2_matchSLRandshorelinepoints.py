#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov  3 10:55:57 2025

@author: useradmin-yshe948

ID mapping summary:
- Rates side:
    shoreline points already include retreat-rate fields from preprocess1
    (e.g., NSM, WLR, Start_date, End_date, Duration). No extra rates join here.
- SLR side:
    NZ_VLM `Site ID` --(exact join)--> NZSeaRise `site`
    shoreline point --(nearest)--> joined SLR point (`Site ID`/`site`)

Important: this script only adds SLR nearest-point attributes to shoreline points
and preserves existing shoreline/rate fields.
"""
import pandas as pd
import geopandas as gpd
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from tqdm import tqdm
from shapely.geometry import LineString
import contextily as ctx

# input shoreline points (use dunepeak output to preserve dune metrics)
inputshorelinepoints = r"output/dunepeak"
shorelinepointfilename = "merged"
inputshorelinepointsfilename = "dunepeak_pct5_fw5_bw20_s5.gpkg"

## input SLR
IDposition_folder = r"input/SLR_OCC"
IDposition_filename = "NZ_VLM_final_May24.csv"
SLR_folder = r"input/SLR_OCC"
SLR_filename = "NZSeaRise_proj_novlm.csv"
outputloc = "input/SLR"

# output figure
outputfigname = f"{shorelinepointfilename}_SLR_match.png"
outputfilename = f"{shorelinepointfilename}_SLR_match.gpkg"

## these value only for do match the longtitude and latitude between NZ_VLM_final_May24.csv and NZSeaRise_proj_novlm.csv
confidence_level = "low_confidence"
year = 2020
scenario = 2.6

# currentlocation
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder, outputloc), exist_ok=True)

# clean lon and lat in SLR raw files
df_ID = pd.read_csv(
    os.path.join(grandparent_folder, IDposition_folder, IDposition_filename)
)
df_ID = df_ID[["Site ID", "Lon", "Lat"]]
print(df_ID.head())
df_SLR = pd.read_csv(os.path.join(grandparent_folder, SLR_folder, SLR_filename))
print(df_SLR.head())

print("year:", df_SLR["year"].unique())
print("scenario:", df_SLR["scenario"].unique())
print("confidence level:", df_SLR["Confidence"].unique())
print("site", df_SLR["site"].unique())

df_SLR_selected = df_SLR[
    (df_SLR["year"] == year)
    & (df_SLR["scenario"] == scenario)
    & (df_SLR["Confidence"] == confidence_level)
]
df_SLR_selected = df_SLR_selected[["site"]]

merge_df = pd.merge(
    df_ID, df_SLR_selected, left_on="Site ID", right_on="site", how="inner"
)

# Convert to GeoDataFrame
SLRpoints = gpd.GeoDataFrame(
    merge_df,
    geometry=gpd.points_from_xy(merge_df.Lon, merge_df.Lat),
    crs="EPSG:4326",  # WGS84 latitude/longitude
)

# load shoreline point data
lastestuniquepoints = gpd.read_file(
    os.path.join(grandparent_folder, inputshorelinepoints, inputshorelinepointsfilename)
)
print("shoreline/dunepeak points CRS:", lastestuniquepoints.crs)

# -----------------------------------------------------------------------------
# Rates are already attached to latest shoreline/dunepeak points (from preprocess1).
# Keep the same object name for downstream logic.
# -----------------------------------------------------------------------------
shore_with_rates = lastestuniquepoints.copy()
print(
    "using rates from shoreline input:",
    int(shore_with_rates["WLR"].notna().sum()) if "WLR" in shore_with_rates.columns else 0,
    "shoreline points with non-null WLR",
)

# load SLR file
# SLRpoints=gpd.read_file(os.path.join(grandparent_folder, inputSLRfolder,inputSLRfilename))
# print("SLR points CRS:", SLRpoints.crs)

if SLRpoints.crs != lastestuniquepoints.crs:
    SLRpoints = SLRpoints.to_crs(lastestuniquepoints.crs)
print("SLR points CRS:", SLRpoints.crs)

SLRpoints["SLR_X"] = SLRpoints.geometry.x
SLRpoints["SLR_Y"] = SLRpoints.geometry.y


# --- Perform one-to-one nearest match from shoreline points to SLR points ---
matched = gpd.sjoin_nearest(
    # ID mapping for SLR side: shoreline point -> nearest SLR point, where
    # SLR `Site ID` (from NZ_VLM file) is matched to SLR projection `site` before this join.
    shore_with_rates,
    SLRpoints,
    how="left",
    distance_col="dist_to_SLR_m",
    # unique=True
    #    distance_col="dist_to_SLR"
)
matched = matched.rename(columns={"index_right": "slr_index_right"})
matched["shore_id"] = matched.index  # or use the correct shoreline ID column
matched = matched[~matched.duplicated("shore_id", keep="first")]

print("matching...")
unique_matched = np.sort(matched["slr_index_right"].dropna().unique())

print("plotting...")

lines = gpd.GeoDataFrame(
    {"site": matched.site},
    geometry=matched.apply(
        lambda row: gpd.GeoSeries(
            LineString([(row["point_X"], row["point_Y"]), (row["SLR_X"], row["SLR_Y"])])
        ),
        axis=1,
    )[0],
    crs=matched.crs,
)

ax = lines.to_crs(epsg=3857).plot("site", figsize=(10, 8), linewidth=0.5, cmap="tab20")
ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery)

ax.set_title(
    f"{shorelinepointfilename}_SLR_match total SLR points: {len(unique_matched)}",
    fontsize=40,
)
plt.axis("off")
matched["Unique_ID"] = matched["Unique_ID"].astype(float).astype(int).astype(str)

ax.get_figure().savefig(
    os.path.join(grandparent_folder, outputloc, outputfigname),
    dpi=300,
    bbox_inches="tight",
)
# savedata
matched.to_file(
    os.path.join(grandparent_folder, outputloc, outputfilename), driver="gpkg"
)
