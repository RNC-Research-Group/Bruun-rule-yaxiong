#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov  4 19:11:02 2025

@author: yaxio
"""
import os
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
import numpy as np
# input loc
shorelinepointfilename="JaMoNoRaSoWa"#JaMoNoRaSoWa
inputfolderloc=r"output/brunnrule"
buffer_dist=10
confidence_level='medium_confidence'
year=2150
percentile=0.5
scenario=4.5
inputfilename=f"brunnrule_{shorelinepointfilename}_buffer_{buffer_dist}.gpkg"
outputfolderloc=r"output/brunnrule"

outputfilename_gpkg=f"brunnrule_{shorelinepointfilename}_b_{buffer_dist}_{confidence_level}_y_{year}_s_{scenario}_p_{percentile}.gpkg"
outputfilename_shp=f"brunnrule_{shorelinepointfilename}_b_{buffer_dist}_{confidence_level}_y_{year}_s_{scenario}_p_{percentile}.shp"
SLR_loc=r"input/SLR"
SLR_matchfile=f"{shorelinepointfilename}_SLR_match.gpkg"

SLR_scenariofile=f"{confidence_level}_y_{year}_s_{scenario}.gpkg"
currentyear=2020 #The current year is used to calculate the erosion rate. Ideally, it should correspond to the mean date of the most recent shoreline points.

# current folder
current_script = os.path.abspath(__file__)
grandparent_folder =  os.path.dirname(os.path.dirname(current_script))

# SLR data
SLR_match=gpd.read_file(os.path.join(grandparent_folder, SLR_loc,SLR_matchfile))
SLR_scenario=gpd.read_file(os.path.join(grandparent_folder, SLR_loc,SLR_scenariofile))
print(SLR_match.crs)
print(SLR_scenario.crs)
data=gpd.read_file(os.path.join(grandparent_folder,inputfolderloc,inputfilename))
print(data.crs)
SLR_scenario=SLR_scenario.to_crs(data.crs)
print(SLR_scenario.crs)

n_data=len(data)

exportdata = gpd.GeoDataFrame(columns=data.columns, 
                                   geometry='geometry',
                                   crs=data.crs)

for _, row in tqdm(data.iterrows(),total=n_data,desc="processing transects"):
    uniqueID_transect=row["Unique_ID"]
    match_SLR = SLR_match[SLR_match["Unique_ID"] == uniqueID_transect]
    SLR_siteID=match_SLR["Site ID"].iloc[0]
    match_SLR_senario=SLR_scenario[SLR_scenario["Site ID"]==SLR_siteID]
    row["S_SLR"]=match_SLR_senario[f"{percentile}"].iloc[0]
    if pd.notna(row["R"]):
        row["R_SLR"]=row["S_SLR"]*row["R"]
        row["ER_SLR"]=row["R_SLR"]/(year-currentyear)
    else:
        row["R_SLR"]=np.nan
        row["ER_SLR"]=np.nan
        
    exportdata = pd.concat([exportdata, gpd.GeoDataFrame([row], crs=data.crs)], ignore_index=True)    


exportdata.set_crs(data.crs, inplace=True)
exportdata.to_file(os.path.join(grandparent_folder,outputfolderloc,outputfilename_shp), driver="ESRI Shapefile")
exportdata.to_file(os.path.join(grandparent_folder,outputfolderloc,outputfilename_gpkg), driver="GPKG")