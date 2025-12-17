#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 22 13:26:19 2025

@author: yshe948
"""
import matplotlib.pyplot as plt
import os
import pandas as pd
import numpy as np
import xarray as xr
import geopandas as gpd
from tqdm.auto import tqdm

# input
inputloc = r"input/wavedata"
shorelinepointfilename = "JaMoNoRaSoWa"  # JaMoNoRaSoWa

# output
outputloc = r"input/wavedata/WGselected"

# current folder
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))

# Date range
mindate = pd.to_datetime("1979-01-01 00:00:00")
maxdate = pd.to_datetime("2024-01-01 00:00:00")

outputfile_gpkg = (
    f"wavedatasum_{shorelinepointfilename}_{mindate.date()}_{maxdate.date()}.gpkg"
)
outputfile_shp = (
    f"wavedatasum_{shorelinepointfilename}_{mindate.date()}_{maxdate.date()}.shp"
)
# Variables to process
variables = ["hs", "t01", "t02", "fp", "t0m1"]
g = 9.81

# Read gauge file
WG_locations = os.path.join(
    grandparent_folder, inputloc, f"WGselected/WGselected_{shorelinepointfilename}.gpkg"
)
gdf_WG = gpd.read_file(WG_locations)
target_points = gdf_WG["seapoint"].astype(int).unique()
n_points = len(target_points)

data_dict = {}

# === Loop through all variables ===
# 5/5 [22:03<00:00, 264.80s/it]
for var in tqdm(variables):
    print(f"\n📘 Processing variable: {var}")

    folder = os.path.join(grandparent_folder, inputloc, f"whacs_{var}")
    all_files = sorted([f for f in os.listdir(folder) if f.endswith(".nc")])

    var_all = []  # store monthly aligned data
    time_all = []  # store time vectors

    for f in tqdm(all_files):
        parts = f.split("_")[-1].replace(".nc", "")
        start_str, end_str = parts.split("-")
        start = pd.to_datetime(start_str, format="%Y%m%d%H%M")
        end = pd.to_datetime(end_str, format="%Y%m%d%H%M")

        if (end >= mindate) and (start <= maxdate):
            filepath = os.path.join(folder, f)
            # print(f"  Reading {f}")
            ds = xr.open_dataset(filepath)

            seapoint = ds["seapoint"].values
            var_data = ds[var].values  # get variable values
            time = pd.to_datetime(ds["time"].values)

            # Create aligned array (all NaN initially)
            var_aligned = np.full((var_data.shape[0], n_points), np.nan)

            # Find matching seapoints between target and file
            common, idx_ref, idx_cur = np.intersect1d(
                target_points, seapoint, return_indices=True
            )

            # Fill matching data
            var_aligned[:, idx_ref] = var_data[:, idx_cur]

            # print(f"    {len(common)} / {n_points} seapoints matched")

            var_all.append(var_aligned)
            time_all.append(time)

            ds.close()

    # Combine all months into continuous array
    if var_all:
        var_all = np.concatenate(var_all, axis=0)
        time_all = np.concatenate(time_all, axis=0)
        print(f"✅ {var} combined: shape {var_all.shape}")
        data_dict[var] = var_all
    else:
        print(f"⚠️ No data found for {var} within date range.")

hs = data_dict["hs"]  # shape (time, n_points)
t01 = data_dict["t01"]  # same shape
t02 = data_dict["t02"]
t0m1 = data_dict["t0m1"]
fp = data_dict["fp"]
time = time_all  # time vector, same for all


# Create an empty list to collect results
sum_results = []
for i in tqdm(range(n_points)):
    hs_i = hs[:, i]
    t01_i = t01[:, i]
    t02_i = t02[:, i]
    t0m1_i = t0m1[:, i]
    fp_i = fp[:, i]
    seapoint = target_points[i]

    df_point = pd.DataFrame(
        {"Hs": hs_i, "T01": t01_i, "T02": t02_i, "T0m1": t0m1_i, "Fp": fp_i}
    )
    df_point_sorted = df_point.sort_values(by="Hs", ascending=False).reset_index(
        drop=True
    )
    exceedance_prob = 12 / (24 * 365)  # 12 h out of one year
    rank_index = int(
        np.round(exceedance_prob * len(time) - 1)
    )  # 0-based index in python
    Hs12h = df_point_sorted.loc[rank_index, "Hs"]
    T0112h = df_point_sorted.loc[rank_index, "T01"]
    T0212h = df_point_sorted.loc[rank_index, "T02"]
    T0m112h = df_point_sorted.loc[rank_index, "T0m1"]
    Fp12h = df_point_sorted.loc[rank_index, "Fp"]
    Tp12h = np.nan if np.isnan(Fp12h) or Fp12h == 0 else 1.0 / Fp12h
    Tmean = np.mean([T0112h, T0212h, T0m112h, Tp12h])
    CD = 2.28 * Hs12h - 68.5 * Hs12h**2 / (g * Tmean**2)

    df_sum = pd.DataFrame(
        [
            {
                "seapoint": seapoint,
                "Hs_12h_y": Hs12h,
                "T01_12h_y": T0112h,
                "T02_12h_y": T0212h,
                "T0m1_12h_y": T0m112h,
                "Tp_12h_y": Tp12h,
                "Tmean": Tmean,
                "CD": CD,
            }
        ]
    )
    sum_results.append(df_sum)

sum_results_all = pd.concat(sum_results, ignore_index=True)

# Merge the results with gdf_WG based on the 'seapoint' column
gdf_sum = gdf_WG[["seapoint", "geometry"]].merge(
    sum_results_all, on="seapoint", how="right"
)

# Convert to GeoDataFrame (inherits CRS from gdf_WG)
gdf_sum = gpd.GeoDataFrame(gdf_sum, geometry="geometry", crs=gdf_WG.crs)
gdf_sum.to_file(
    os.path.join(grandparent_folder, outputloc, outputfile_gpkg), driver="GPKG"
)
gdf_sum.to_file(
    os.path.join(grandparent_folder, outputloc, outputfile_shp), driver="ESRI Shapefile"
)
print("Computed H12h/y, T12h/y, and Fp12h/y for all seapoints.")

# Define which variables to plot (Hs and the period variables)
vars_to_plot = [
    "Hs_12h_y",
    "T01_12h_y",
    "T02_12h_y",
    "T0m1_12h_y",
    "Tp_12h_y",
    "Tmean",
    "CD",
]

# Loop over variables and create one figure per variable
for var in tqdm(vars_to_plot):
    fig, ax = plt.subplots(figsize=(8, 6))
    im = gdf_sum.plot(
        column=var,
        ax=ax,
        legend=True,
        cmap="jet",
        markersize=40,
        edgecolor="none",
        linewidth=0.3,
    )
    mean_var = gdf_sum[var].mean()
    std_var = gdf_sum[var].std()
    # Access the colorbar and set the label
    cbar = im.get_figure().axes[-1]  # colourbar axis is the last axis
    if var == "Hs_12h_y":
        cbar.set_ylabel("Significant wave height (m)", fontsize=10)
    elif var == "CD":
        cbar.set_ylabel("CD (m)", fontsize=10)
    else:
        cbar.set_ylabel("Wave period (s)", fontsize=10)

    if var == "Hs_12h_y" or var == "CD":
        ax.set_title(
            f"{shorelinepointfilename}: {mindate.date()}-{maxdate.date()}\n {var}={mean_var:.1f}±{std_var:.1f} m",
            fontsize=10,
        )
    else:
        ax.set_title(
            f"{shorelinepointfilename}: {mindate.date()}-{maxdate.date()}\n {var}={mean_var:.1f}±{std_var:.1f} s",
            fontsize=10,
        )

    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal")
    plt.tight_layout()
    plt.show()

    # Save the figure (PNG or PDF)
    fig_path = os.path.join(
        grandparent_folder,
        outputloc,
        f"{shorelinepointfilename}_{mindate.date()}-{maxdate.date()}_{var}.png",
    )
    fig.savefig(fig_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
