#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 30 14:24:32 2025

@author: yshe948
"""

import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from slr_settings import CONFIDENCE_LEVEL, YEARS, SCENARIOS, PERCENTILES_FLOAT

IDposition_folder = "input/SLR_OCC"
IDposition_filename = "NZ_VLM_final_May24.csv"
SLR_folder = "input/SLR_OCC"
SLR_filename = "NZSeaRise_proj_novlm.csv"
outputloc = "input/SLR"

current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder, outputloc), exist_ok=True)

confidence_level = CONFIDENCE_LEVEL
years = YEARS
scenarios = SCENARIOS
percentiles = PERCENTILES_FLOAT

df_ID = pd.read_csv(
    os.path.join(grandparent_folder, IDposition_folder, IDposition_filename)
)
df_ID = df_ID[
    [
        "Site ID",
        "Lon",
        "Lat",
        "Vertical Rate (mm/yr)",
        "Vertical Rate - BOP corrected (mm/yr)",
        "1-sigma uncertainty (mm/yr)",
        "Number of obs",
        "Quality Factor",
        "Average distance between coastal point and observations",
    ]
]
print(df_ID.head())
df_SLR = pd.read_csv(os.path.join(grandparent_folder, SLR_folder, SLR_filename))
print(df_SLR.head())

print("year:", df_SLR["year"].unique())
print("scenario:", df_SLR["scenario"].unique())
print("confidence level:", df_SLR["Confidence"].unique())
print("site", df_SLR["site"].unique())

for year in years:
    for scenario in scenarios:
        figname = f"{confidence_level}_y_{year}_s_{scenario}.png"
        gpkgfilename = f"{confidence_level}_y_{year}_s_{scenario}.gpkg"

        df_SLR_selected = df_SLR[
            (df_SLR["year"] == year)
            & (df_SLR["scenario"] == scenario)
            & (df_SLR["Confidence"] == confidence_level)
        ]

        if df_SLR_selected.empty:
            print(f"No SLR rows found for year={year}, scenario={scenario}, confidence={confidence_level}")
            continue

        merge_df = pd.merge(
            df_ID, df_SLR_selected, left_on="Site ID", right_on="site", how="inner"
        )

        if merge_df.empty:
            print(f"No merged rows for year={year}, scenario={scenario}")
            continue

        gdf_ID = gpd.GeoDataFrame(
            merge_df,
            geometry=gpd.points_from_xy(merge_df.Lon, merge_df.Lat),
            crs="EPSG:4326",
        )

        fig, axes = plt.subplots(
            1, len(percentiles), figsize=(15, 6), sharex=True, sharey=True
        )
        for i, percentile in enumerate(percentiles):
            ax = axes[i]
            im = gdf_ID.plot(f"{percentile}", ax=ax, legend=True, cmap="jet")
            ax.set_title(
                f"{confidence_level}; year={year}; \n percentile={percentile}; scenario={scenario}"
            )
            ax.set_xlabel("Lon")
            ax.set_ylabel("Lat")
            cbar = im.get_figure().axes[-1]
            cbar.set_ylabel("SLR (m)", fontsize=10)

        fig.savefig(
            os.path.join(grandparent_folder, outputloc, figname),
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig)

        out_path = os.path.join(grandparent_folder, outputloc, gpkgfilename)
        gdf_ID.to_file(out_path, driver="GPKG")
        print(f"Saved: {out_path}")
