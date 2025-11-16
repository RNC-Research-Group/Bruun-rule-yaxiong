# -*- coding: utf-8 -*-
"""
Created on Thu Oct 23 09:43:54 2025

@author: yshe948
"""
from glob import glob
import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from tqdm import tqdm

# output
outputloc = r"input\shorelinepoints"

# locate folder
current_script = os.path.abspath(__file__)
grandparent_folder =  os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder,outputloc), exist_ok=True)

# input
to_keep=['Unique_ID','Date','Distance','geometry']
crsused='3994'
inputfolder = os.path.join(grandparent_folder,"input\Merged Intersects_UniqueID")#Merged Intersects_UniqueID_test only Waihekeisland as an eample to test

to_drop=[]
files = sorted(glob(os.path.join(inputfolder, "*.shp")))
pointsall=[]
prefixes=[]
for file in files:
    filename = os.path.basename(file)
    name_no_ext = os.path.splitext(filename)[0]    # 'WaihekeIsland_Intersects'
    prefix = name_no_ext[:2]                       # 'Wa'
    prefixes.append(prefix)
    points_individualfile=gpd.read_file(file)
    for col in points_individualfile.columns:
        if col not in to_keep:
            to_drop.append(col)
            
    points_individualfile.drop(to_drop,axis=1,inplace=True)    
    pointsall.append(points_individualfile)
    del points_individualfile
    
merged_prefixes = "".join(prefixes)    
    
points = gpd.GeoDataFrame(pd.concat(pointsall, ignore_index=True), crs=pointsall[0].crs)
points = points.to_crs(epsg=crsused)

outputfile_path_points_gpkg=os.path.join(grandparent_folder,outputloc,f'lastestuniquepoints_{merged_prefixes}.gpkg')
outputfile_path_points_shp=os.path.join(grandparent_folder,outputloc,f'lastestuniquepoints_{merged_prefixes}.shp')

def get_unique_lastest_point(points):
    unique_IDs=points.Unique_ID.unique().tolist()
    subsets=[]

    for tid in tqdm(unique_IDs, desc="Processing transects", ncols=80):#unique_IDs:
        # only use the lastest date of each points in shape file
        subset = points[points.Unique_ID == tid]
        seaward_point_distance=subset['Distance'].min()
        landward_point_distance=subset['Distance'].max()        
        seaward_point=subset[subset['Distance'] == seaward_point_distance].copy()
        landward_point=subset[subset['Distance'] == landward_point_distance].copy()
        seaward_geom = seaward_point.geometry.iloc[0]
        landward_geom = landward_point.geometry.iloc[0]
        
        dx_line1 = - seaward_geom.x + landward_geom.x
        dy_line1 = - seaward_geom.y + landward_geom.y
        length1 = np.hypot(dx_line1, dy_line1)
        
        # Unit vector in the transect direction
        ux1, uy1 = dx_line1 / length1, dy_line1 / length1
        
        latest_date = subset['Date'].max()
        subset_latest = subset[subset['Date'] == latest_date].copy()
        subset_latest.loc[:, 'ux1'] = ux1
        subset_latest.loc[:, 'uy1'] = uy1
        subsets.append(subset_latest)
    # Combine them all into one DataFrame
    lastestuniquepoints = gpd.GeoDataFrame(pd.concat(subsets, ignore_index=True))
    return(lastestuniquepoints)

lastestuniquepoints=get_unique_lastest_point(points)
lastestuniquepoints["point_X"]=lastestuniquepoints.geometry.x
lastestuniquepoints["point_Y"]=lastestuniquepoints.geometry.y

## save data
lastestuniquepoints.to_file(outputfile_path_points_gpkg, driver="GPKG")

lastestuniquepoints["Unique_ID"] = lastestuniquepoints["Unique_ID"].apply(
    lambda x: str(int(x)) if pd.notna(x) else ""
) 

lastestuniquepoints.to_file(outputfile_path_points_shp, driver="ESRI Shapefile")

## figure
fig1, ax1 = plt.subplots(figsize=(100, 100))
plt.scatter(lastestuniquepoints["point_X"], lastestuniquepoints["point_Y"],
            c='red', s=1, alpha=0.7, edgecolors='red',label='Points')
ax1.set_aspect('equal')

fig1.savefig(os.path.join(grandparent_folder,outputloc,f'lastestuniquepoints_{merged_prefixes}.png'), dpi=300, bbox_inches='tight')        
plt.close(fig1)
