# -*- coding: utf-8 -*-
"""
Created on Fri Oct 17 15:23:09 2025

@author: yshe948
"""
#%reset -f

import geopandas as gpd
import matplotlib.pyplot as plt
import os
import pandas as pd
import xarray as xr

# input
shorelinepointfileloc=r'input/shorelinepoints'
shorelinepointfilename="JaMoNoRaSoWa"#JaMoNoRaSoWa
buffer_dist = 14000  # unit m for search wave gauge
wavedatafile = r"input/wavedata/whacs_fp/fp_WHACS_hindcast_WHACS_ERA5_1hr_197901010000-197901312300.nc"

# output
outputloc="input/wavedata/WGselected"
outputfilenamegpkg=f"WGselected_{shorelinepointfilename}.gpkg"
outputfilenamejpg=f"WGselected_{shorelinepointfilename}.jpg"

# xlim and ylim for plot
x0=1*10**6
x1=2.2*10**6
y0=4.7*10**6
y1=6.25*10**6

# currentlocation
current_script = os.path.abspath(__file__)
grandparent_folder =  os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder,outputloc), exist_ok=True)

# --- Load your polygon ---
gdf = gpd.read_file(os.path.join(grandparent_folder,shorelinepointfileloc, f"lastestuniquepoints_{shorelinepointfilename}.gpkg"))
print("shp CRS:", gdf.crs)

# process wave gauge location
ds = xr.open_dataset(os.path.join(grandparent_folder,wavedatafile))

lon = ds["longitude"].values  # numpy array, shape (17422,)
lat = ds["latitude"].values   # numpy array, shape (17422,)
seapoint=ds["seapoint"].values

df = pd.DataFrame({
    "latitude": lat,
    "longitude": lon,
    "seapoint": seapoint
})

# Drop duplicates based only on latitude & longitude
df_unique = df.drop_duplicates(subset=["latitude", "longitude"]).reset_index(drop=True)

# build up gdf
gdf_wave = gpd.GeoDataFrame(
    df_unique,
    geometry=gpd.points_from_xy(df_unique["longitude"], df_unique["latitude"]),
    crs="EPSG:4326"
)

# match crs
if gdf_wave.crs != gdf.crs:
    gdf_wave = gdf_wave.to_crs(gdf.crs)
    
print("wave CRS:", gdf_wave.crs)

# --- Buffer polygon (expand) ---
gdf_buffered = gdf.buffer(buffer_dist)

# --- Combine (union) original + buffer ---
combined = gdf.union_all().union(gdf_buffered.union_all())

# --- Convert to GeoDataFrame for saving and plotting ---
gdf_combined = gpd.GeoDataFrame(geometry=[combined], crs=gdf.crs)

# Select points within the combined polygon
gdf_wave_selected = gdf_wave[gdf_wave.within(gdf_combined.geometry.iloc[0])].reset_index(drop=True)
gdf_wave_selected = gdf_wave_selected[["seapoint","latitude", "longitude", "geometry"]]
print(f"Number of gauges inside the combined area: {len(gdf_wave_selected)}")

# --- Visualise ---
fig, ax = plt.subplots(figsize=(30, 30), dpi=300)
gdf.plot(ax=ax, color="blue", linewidth=1.5, label="Shoreline points",zorder=0)
gdf_combined.boundary.plot(ax=ax, color="green", linewidth=2, label=f"Original + Buffer={buffer_dist:.0f} m",zorder=1)
gdf_wave.plot(ax=ax,color="black",marker='+',label='All WG',markersize=30, alpha=0.5,zorder=2)
gdf_wave_selected .plot(ax=ax, color="none",edgecolor="red", marker='o', 
    label=f"WG selected ({len(gdf_wave_selected):.0f})", markersize=50,zorder=3)
ax.set_title(f"{shorelinepointfilename}", fontsize=14)
ax.legend(loc="upper right")
# ax.set_xlim(x0,x1)
# ax.set_ylim(y0,y1)
ax.set_xlabel('x (m)')
ax.set_ylabel('y (m)')
ax.set_aspect("equal")
plt.show()

#sys.exit()
# savedata
gdf_wave_selected.to_file(os.path.join(grandparent_folder,outputloc,outputfilenamegpkg),driver="GPKG")
fig.savefig(os.path.join(grandparent_folder,outputloc,outputfilenamejpg), dpi=300, bbox_inches='tight')  
