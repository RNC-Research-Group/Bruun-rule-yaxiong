# -*- coding: utf-8 -*-
"""
Created on Mon Nov  3 10:55:57 2025

@author: useradmin-yshe948
"""
import pandas as pd
import geopandas as gpd
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from tqdm import tqdm

# input shoreline points 
inputshorelinepoints=r"input\shorelinepoints"
shorelinepointfilename="JaMoNoRaSoWa"#"JaMoNoRaSoWa"#Wa
inputshorelinepointsfilename=f"lastestuniquepoints_{shorelinepointfilename}.gpkg"

## input SLR
IDposition_folder=r'input\SLR_OCC'
IDposition_filename='NZ_VLM_final_May24.csv'
SLR_folder=r'input\SLR_OCC'
SLR_filename='NZSeaRise_proj_novlm.csv'
outputloc="input\SLR"

# output figure
outputfigname=f"{shorelinepointfilename}_SLR_match.png"
outputfilename=f"{shorelinepointfilename}_SLR_match.gpkg"

## these value only for do match the longtitude and latitude between NZ_VLM_final_May24.csv and NZSeaRise_proj_novlm.csv
confidence_level='low_confidence'
year=2020
scenario=2.6

# currentlocation
current_script = os.path.abspath(__file__)
grandparent_folder =  os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder,outputloc), exist_ok=True)

# clean lon and lat in SLR raw files
df_ID=pd.read_csv(os.path.join(grandparent_folder,IDposition_folder,IDposition_filename))
df_ID=df_ID[["Site ID","Lon","Lat"]]
print(df_ID.head())
df_SLR=pd.read_csv(os.path.join(grandparent_folder,SLR_folder,SLR_filename))
print(df_SLR.head())

print("year:",df_SLR["year"].unique())
print("scenario:",df_SLR["scenario"].unique())
print("confidence level:",df_SLR["Confidence"].unique())
print("site",df_SLR["site"].unique())

df_SLR_selected=df_SLR[(df_SLR["year"]==year) & (df_SLR["scenario"]==scenario) & (df_SLR["Confidence"]==confidence_level)]
df_SLR_selected=df_SLR_selected[["site"]]

merge_df=pd.merge(df_ID,df_SLR_selected,left_on='Site ID',right_on='site', how='inner')

# Convert to GeoDataFrame
SLRpoints = gpd.GeoDataFrame(
    merge_df,
    geometry=gpd.points_from_xy(merge_df.Lon, merge_df.Lat),
    crs="EPSG:4326"  # WGS84 latitude/longitude
)

# load shoreline point data
lastestuniquepoints=gpd.read_file(os.path.join(grandparent_folder, inputshorelinepoints,inputshorelinepointsfilename))
print("shoreline points CRS:", lastestuniquepoints.crs)

# load SLR file
#SLRpoints=gpd.read_file(os.path.join(grandparent_folder, inputSLRfolder,inputSLRfilename))
#print("SLR points CRS:", SLRpoints.crs)

if SLRpoints.crs != lastestuniquepoints.crs:
    SLRpoints=SLRpoints.to_crs(lastestuniquepoints.crs)    
print("SLR points CRS:", SLRpoints.crs)

SLRpoints["SLR_X"]=SLRpoints.geometry.x
SLRpoints["SLR_Y"]=SLRpoints.geometry.y


# --- Perform one-to-one nearest match ---
matched = gpd.sjoin_nearest(
    lastestuniquepoints, 
    SLRpoints, 
    how="left", 
    #unique=True
#    distance_col="dist_to_SLR"
)
matched['shore_id'] = matched.index  # or use the correct shoreline ID column
matched = matched[~matched.duplicated('shore_id', keep='first')]

print("matching...")
unique_matched=np.sort(matched["index_right"].unique())

print("plotting...")

fig2, ax2 = plt.subplots(figsize=(100, 80))
#fig2, ax2 = plt.subplots(figsize=(6, 4))
n_c = len(unique_matched)

colors = cm.rainbow(np.linspace(0, 1, n_c))

for i,color in tqdm(zip(unique_matched, colors), total=n_c, desc="Drawing connections"):
    subset = matched[matched["index_right"] == i]
    n_subset=len(subset)
    plt.scatter(
        matched.loc[matched["index_right"] == i, "point_X"],
        matched.loc[matched["index_right"] == i, "point_Y"],
        color=color, s=0.5, alpha=0.4, edgecolors=color, marker='o', zorder=1#label='points'
    )
    plt.scatter(
        matched.loc[matched["index_right"] == i, "SLR_X"],
        matched.loc[matched["index_right"] == i, "SLR_Y"],
        color=color, s=0.5, alpha=0.4, edgecolors=color, marker='s', 
        label=f'SLR points {i:.0f}: ({n_subset:.0f})', zorder=2
    )
    
    for _, row in subset.iterrows():
       ax2.plot(
           [row["point_X"], row["SLR_X"]],
           [row["point_Y"], row["SLR_Y"]],
           color=color, linewidth=0.1, alpha=0.1, zorder=3
           )
    del row

ax2.set_title(f"{shorelinepointfilename}_SLR_match total SLR points: {n_c}" 
    ,fontsize=40)
plt.axis("off")
matched["Unique_ID"] = matched["Unique_ID"].astype(float).astype(int).astype(str)

fig2.savefig(os.path.join(grandparent_folder,outputloc,outputfigname), dpi=300, bbox_inches='tight')
# savedata
matched.to_file(os.path.join(grandparent_folder,outputloc,outputfilename),driver='gpkg')