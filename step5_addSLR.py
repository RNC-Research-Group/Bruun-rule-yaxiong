#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov  4 19:11:02 2025

@author: yaxio
"""
import os
import pandas as pd
import geopandas as gpd

# input loc
shorelinepointfilename = "JaMoNoRaSoWa"  # JaMoNoRaSoWa
inputfolderloc = r"output/brunnrule"
buffer_dist = 10
confidence_level = "medium_confidence"
year = 2150
percentile = "0.5"
scenario = 4.5
inputfilename = f"brunnrule_{shorelinepointfilename}_buffer_{buffer_dist}.gpkg"
outputfolderloc = r"output/brunnrule"

SLR_loc = r"input/SLR"
SLR_matchfile = f"{shorelinepointfilename}_SLR_match.gpkg"

SLR_scenariofile = f"{confidence_level}_y_{year}_s_{scenario}.gpkg"
currentyear = 2020  # The current year is used to calculate the erosion rate. Ideally, it should correspond to the mean date of the most recent shoreline points.

# current folder
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))

# SLR data
SLR_match = gpd.read_file(os.path.join(grandparent_folder, SLR_loc, SLR_matchfile))
SLR_scenario = gpd.read_file(
    os.path.join(grandparent_folder, SLR_loc, SLR_scenariofile)
)
print(os.path.join(grandparent_folder, SLR_loc, SLR_matchfile), SLR_match.crs)
print(os.path.join(grandparent_folder, SLR_loc, SLR_scenariofile), SLR_scenario.crs)
data = gpd.read_file(os.path.join(grandparent_folder, inputfolderloc, inputfilename))
print(os.path.join(grandparent_folder, inputfolderloc, inputfilename), data.crs)
SLR_scenario = SLR_scenario.to_crs(data.crs)
print(os.path.join(grandparent_folder, SLR_loc, SLR_scenariofile), SLR_scenario.crs)
years_delta = year - currentyear

# Vectorized lookup to avoid per-row filtering
# Ensure indices are unique before mapping
site_lookup = (
    SLR_match.drop_duplicates(subset="Unique_ID").set_index("Unique_ID")["Site ID"]
)
scenario_lookup = (
    SLR_scenario.drop_duplicates(subset="Site ID").set_index("Site ID")[percentile]
)

data["Site ID"] = data["Unique_ID"].map(site_lookup)
data["S_SLR"] = data["Site ID"].map(scenario_lookup)
data["R_SLR"] = data["S_SLR"] * data["R"]
data["ER_SLR"] = data["R_SLR"] / years_delta

data["lat"] = data.geometry.to_crs(4326).y
data["lon"] = data.geometry.to_crs(4326).x

wave_points = gpd.points_from_xy(data.wave_X, data.wave_Y, crs=data.crs).to_crs(4326)
data["wave_lat"] = wave_points.y
data["wave_lon"] = wave_points.x

cols_for_map = ['Unique_ID', 'dist_m', 'mean_dist_to_coast', 'CD', 'B', 'L', 'R', 'tanbeta', 'S_SLR', 'R_SLR', 'ER_SLR', 'lat', 'lon', 'wave_lat', 'wave_lon']
print(data[cols_for_map])
data[cols_for_map].to_parquet(
    os.path.join(f"brunnrule_{shorelinepointfilename}_b_{buffer_dist}_{confidence_level}_y_{year}_s_{scenario}_p_{percentile}.parquet")
)

# data.to_file(
#     os.path.join(grandparent_folder, outputfolderloc, outputfilename_shp),
#     driver="ESRI Shapefile",
# )
# data.to_file(
#     os.path.join(grandparent_folder, outputfolderloc, outputfilename_gpkg),
#     driver="GPKG",
# )