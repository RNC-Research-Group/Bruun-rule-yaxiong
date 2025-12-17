#!/usr/bin/env python3
import os
import pandas as pd
import geopandas as gpd

# input loc
buffer_dist = 10
confidence_level = "medium_confidence"
year = 2150
percentile = "0.5"
scenario = 4.5

# Note the typo here, brunnrule instead of bruunrule
inputfilename = f"../output/brunnrule/brunnrule_JaMoNoRaSoWa_buffer_{buffer_dist}.gpkg"
SLR_matchfile = f"../input/SLR/JaMoNoRaSoWa_SLR_match.gpkg"
SLR_scenariofile = f"../input/SLR/{confidence_level}_y_{year}_s_{scenario}.gpkg"
currentyear = 2020  # The current year is used to calculate the erosion rate. Ideally, it should correspond to the mean date of the most recent shoreline points.

# SLR data
SLR_match = gpd.read_file(SLR_matchfile)
SLR_scenario = gpd.read_file(SLR_scenariofile)
print(SLR_matchfile, SLR_match.crs)
print(SLR_scenariofile, SLR_scenario.crs)
data = gpd.read_file(inputfilename)
print(inputfilename, data.crs)
SLR_scenario = SLR_scenario.to_crs(data.crs)
print(SLR_scenariofile, SLR_scenario.crs)
years_delta = year - currentyear
print(years_delta)

# Vectorized lookup to avoid per-row filtering
# Ensure indices are unique before mapping
site_lookup = SLR_match.drop_duplicates(subset="Unique_ID").set_index("Unique_ID")[
    "Site ID"
]
scenario_lookup = SLR_scenario.drop_duplicates(subset="Site ID").set_index("Site ID")[
    percentile
]

data["Site ID"] = data["Unique_ID"].map(site_lookup)
#data["S_SLR"] = data["Site ID"].map(scenario_lookup)
#data["R_SLR"] = data["S_SLR"] * data["R"]
#data["ER_SLR"] = data["R_SLR"] / years_delta

data["lat"] = data.geometry.to_crs(4326).y
data["lon"] = data.geometry.to_crs(4326).x

wave_points = gpd.points_from_xy(data.wave_X, data.wave_Y, crs=data.crs).to_crs(4326)
data["wave_lat"] = wave_points.y
data["wave_lon"] = wave_points.x

cols_for_map = [
    "Unique_ID",
    "dist_m",
    "mean_dist_to_coast",
    "CD",
    "B",
    "L",
    "R",
    "tanbeta",
    "Site ID",
    #"S_SLR",
    #"R_SLR",
    #"ER_SLR",
    "lat",
    "lon",
    "wave_lat",
    "wave_lon",
]
print(data[cols_for_map])
data[cols_for_map].to_csv(f"bruunrule_JaMoNoRaSoWa_b_{buffer_dist}.csv", index=False, float_format="%.6f")