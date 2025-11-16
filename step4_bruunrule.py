# -*- coding: utf-8 -*-
"""
Created on Sun Oct 26 10:51:48 2025

@author: yshe948
"""

from tqdm import tqdm
import pandas as pd
import geopandas as gpd
import numpy as np
import rasterio as rio
from rasterio.plot import show
import matplotlib.pyplot as plt
import os
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import math
import warnings

# input
shorelinepointfilename="JaMoNoRaSoWa"#JaMoNoRaSoWa
inputloctransect=r"output/match"
transect_wp_gpkg=f'transect_wp_{shorelinepointfilename}.gpkg'
inputlocdunepeak=r"output/dunepeak"
buffer_dist=10
isexportplot=0# 0 do not export the transect; 1 export transect
dunepeak_gpkg=f"{shorelinepointfilename}_dunepeak_{buffer_dist}.gpkg"
bathyfolderloc=r"Z:\Bathymetry250m"
bathyname=r"nzbathy_2016.tif"


outputfigurefolder=f"output/transect_{shorelinepointfilename}_buffer_{buffer_dist}"
outputfolder=r"output/brunnrule"
outputfilename_gpkg=f"brunnrule_{shorelinepointfilename}_buffer_{buffer_dist}.gpkg"
outputfilename_shp=f"brunnrule_{shorelinepointfilename}_buffer_{buffer_dist}.shp"


maxdunepeak=10
extend_landward_m = 200  # meters to extend beyond start
extend_seaward_m = 2000 # meters to extend beyond end
dx_bathy=250
S=1
buffer_plotbathydem = 10000  # metres or coordinate units
#dx_coast=1
# current folder
current_script = os.path.abspath(__file__)
grandparent_folder =  os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder,outputfigurefolder), exist_ok=True)
os.makedirs(os.path.join(grandparent_folder,outputfolder), exist_ok=True)

bathy_path = os.path.join(bathyfolderloc, bathyname)

# load data
transect_wp = gpd.read_file(os.path.join(grandparent_folder, inputloctransect,transect_wp_gpkg))
dunepeak_all = gpd.read_file(os.path.join(grandparent_folder, inputlocdunepeak,dunepeak_gpkg))
dem_bathy = rio.open(bathy_path)

print(transect_wp.crs)
print(dunepeak_all.crs)
print(dem_bathy.crs)


n_transect_wp = len(transect_wp)
num_digits = math.ceil(math.log10(n_transect_wp+1))  # +1 in case n is exactly a power of 10
# Suppose transect_wp is your dataframe


# Number of digits for zero-padding
num_digits = math.ceil(math.log10(n_transect_wp+1))  # +1 in case n is exactly a power of 10
k=1
savetransect_wp = gpd.GeoDataFrame(columns=transect_wp.columns, 
                                   geometry='geometry',
                                   crs=transect_wp.crs)

for _, row in tqdm(transect_wp.iterrows(),total=n_transect_wp,desc="processing transects"):
    
    
    x0, y0 = row["point_X"], row["point_Y"]
    x1, y1 = row["wave_X"], row["wave_Y"]

    # Transect length
    dx_line = x1 - x0
    dy_line = y1 - y0
    length = np.hypot(dx_line, dy_line)

    # Unit vector in the transect direction
    ux, uy = dx_line / length, dy_line / length
    
    # Extended distances along the transect (includes extra before and after)
    distances_bathy = np.arange(-extend_landward_m, length + extend_seaward_m + dx_bathy, dx_bathy)

    # Coordinates along the extended transect
    x_vals_bathy = x0 + ux * distances_bathy
    y_vals_bathy = y0 + uy * distances_bathy
    

    xmin, ymin, xmax, ymax = dem_bathy.bounds
    # Create mask for points inside DEM bounds
    mask1_bathy = (x_vals_bathy >= xmin) & (x_vals_bathy <= xmax) & (y_vals_bathy >= ymin) & (y_vals_bathy <= ymax)
    
    x_vals_bathy = x_vals_bathy[mask1_bathy]
    y_vals_bathy = y_vals_bathy[mask1_bathy]
    distances_bathy_clipped = distances_bathy[mask1_bathy]

    # DEM sample
    coords_bathy = list(zip(x_vals_bathy, y_vals_bathy))
    
    dem_bathy_profile = [val[0] for val in dem_bathy.sample(coords_bathy)]
    
    mask2_bathy = (distances_bathy_clipped >= 0) & (distances_bathy_clipped <= length+extend_seaward_m)

    dist_segment_bathy = distances_bathy_clipped[mask2_bathy]
    dem_segment_bathy = np.array(dem_bathy_profile)[mask2_bathy]
   
    ## find location of CD and dune peak
    target_z = -row.CD
    crossings = np.where(np.diff(np.sign(dem_segment_bathy - target_z)))[0]
    
    intersection_distances = []

    for idx in crossings:
        z1, z2 = dem_segment_bathy[idx], dem_segment_bathy[idx+1]
        dist1, dist2 = dist_segment_bathy[idx], dist_segment_bathy[idx+1]
    
        if z2 != z1:  # avoid division by zero
            dist_cross = dist1 + (target_z - z1) * (dist2 - dist1) / (z2 - z1)
            intersection_distances.append(dist_cross)

    # find the dune peak one
    uniqueID_transect=row["Unique_ID"]
    match = dunepeak_all[dunepeak_all["Unique_ID"] == uniqueID_transect]
    
    coast_elev = match.iloc[0]["coast_elev_m"]
    bathy_elev=match.iloc[0]["bathy_elev_m"]
    
    if pd.notna(coast_elev) and coast_elev < maxdunepeak:
         dunepeak=coast_elev
         choosefrom='coast'
         row["choosefrom"]='coast'
    elif bathy_elev < maxdunepeak:
        dunepeak=bathy_elev
        choosefrom='bathy'
        row["choosefrom"]='bathy'
    else:
        dunepeak=maxdunepeak
        choosefrom='max'
        row["choosefrom"]='max'
    
    if dunepeak<0:
        dunepeak=0
        choosefrom='0'
        row["choosefrom"]='0'
        
        
    # # find the SLR
    # match_SLR = SLR_match[SLR_match["Unique_ID"] == uniqueID_transect]
    # SLR_siteID=match_SLR["Site ID"].iloc[0]
    # match_SLR_senario=SLR_scenario[SLR_scenario["Site ID"]==SLR_siteID]
    
    row["B"]=dunepeak
    # row["S"]=match_SLR_senario[f"{percentile}"].iloc[0] # sea level rise
    row["S"]=1
    #sys.exit()
    wavepointdem=dem_bathy_profile[np.argmin(np.abs(distances_bathy_clipped - length))]
    
    if intersection_distances:
        intersection_median = np.median(intersection_distances)
        #print("Intersection at median distance along transect:", intersection_median)
        row["L"]= intersection_median # horizontal distance between closure depth and dune peak
        row["R"]=S*intersection_median/(dunepeak-target_z)# shoreline recession (m)
        row["tanbeta"]=(dunepeak-target_z)/intersection_median
        row["beta_rad"]=math.atan(row["tanbeta"])
        row["beta_degree"] = math.degrees(row["beta_rad"])
        # row["ER"]=row["R"]/(year-currentyear)
        newx_profile = -row["R"]  # landward from dune peak
        x_new = x0 + row["ux1"] * newx_profile
        y_new = y0 + row["uy1"] * newx_profile  

        row["x_new"]=x_new
        row["y_new"]=y_new
    else:
        intersection_median = None
        print(f"No intersection found along transect segment k = {k}")
        row["L"]= np.nan
        row["R"]= np.nan
        row["tanbeta"]=np.nan
        row["beta_rad"]=np.nan
        row["beta_degree"] = np.nan
        # row["ER"]=np.nan
        row["x_new"]=np.nan
        row["y_new"]=np.nan
    
    if isexportplot==1:
        fig3, ax3 = plt.subplots(figsize=(12, 4))
        
        ax3.scatter(distances_bathy_clipped, dem_bathy_profile,color='none', s=30, alpha=1, 
            edgecolors='blue', marker='o', label='bathy')
        
        ax3.scatter(0, dunepeak,color='green', s=30, alpha=1, 
            edgecolors='green', marker='^', label='dune peak')
        
        ax3.text(
            0, dunepeak,               # data coordinates
            f'dune peak (0, {dunepeak:.1f}) from {choosefrom}',                 # text string
            color='black', fontsize=10, fontweight='bold',
            ha='left', va='bottom',               # text alignment
            rotation=0                            # rotation in degrees
        )
        
        ax3.scatter(length, wavepointdem,color='green',s=30, alpha=1, 
            edgecolors='green', marker='s', label='wave point')
        
        ax3.text(
            length, wavepointdem,               # data coordinates
            f'wave ({length:.0f}, {wavepointdem:.1f})',                 # text string
            color='black', fontsize=10, fontweight='bold',
            ha='left', va='bottom',               # text alignment
            rotation=0                            # rotation in degrees
        )
        
        ax3.plot([distances_bathy_clipped[0],distances_bathy_clipped[-1]],[0,0],
                 color='k',linestyle='--',label='water surface')
        

        
        if intersection_distances:
            ax3.scatter(intersection_distances, np.ones(len(intersection_distances))*target_z,
                        color='purple', s=30, alpha=1, 
            edgecolors='purple', marker='o', label='closure depth all')
            ax3.scatter(intersection_median,target_z,color='pink', s=30, alpha=1, 
            edgecolors='pink', marker='o', label='closure depth median')

            ax3.text(
                intersection_median, target_z,               # data coordinates
                f'CD ({intersection_median:.0f}, {target_z:.1f})',                 # text string
                color='black', fontsize=10, fontweight='bold',
                ha='left', va='bottom',               # text alignment
                rotation=0                            # rotation in degrees
            )
            ax3.set_title(f'Idx: {k-1:.0f} ({row.point_X:.0f}, {row.point_Y:.0f}); '\
                          f'Idx_w: {row.index_right:.0f}; '\
                          f'R = {row.R:.2f} m, when S = {row.S:.1f} m')
        else:
            ax3.set_title(f'({row.point_X:.0f}, {row.point_Y:.0f}) Closure depth could not be determined.')
        
        ax3.legend([f'bathy ({dx_bathy:.0f} m)'],  loc='lower left')
        ax3.set_xlabel('distance (m)')
        ax3.set_ylabel('z (m)')
        #plt.show()
       
        axins = inset_axes(
            ax3,
            width="100%",
            height="100%",
            bbox_to_anchor=(0.45, 0.22, 0.8, 0.8),  # (x0, y0, width, height) in relative figure coords
            bbox_transform=ax3.transAxes,  # interpret coordinates relative to parent axis
            loc='upper right',  # anchor point of the inset box
        )
    

        # Get bounding box between the two points, with a small buffer if needed
        xmin_crop, xmax_crop = sorted([row["point_X"], row["wave_X"]])
        ymin_crop, ymax_crop = sorted([row["point_Y"], row["wave_Y"]])
        
        # Add a small margin (optional)

        xmin_crop -= buffer_plotbathydem
        xmax_crop += buffer_plotbathydem
        ymin_crop -= buffer_plotbathydem
        ymax_crop += buffer_plotbathydem
        
        # Crop DEM to bounding box
        window = rio.windows.from_bounds(xmin_crop, ymin_crop, xmax_crop, ymax_crop, transform=dem_bathy.transform)
        dem_cropped = dem_bathy.read(1, window=window)
        
        # Update transform for the cropped window
        transform_cropped = dem_bathy.window_transform(window)

        # Show DEM in the inset
        show(dem_cropped, transform=transform_cropped, ax=axins, cmap='Greys_r', zorder=0)
        #show(dem_bathy, ax=axins, cmap='Greys_r',zorder=0)
        axins.plot(
            [row["point_X"], row["wave_X"]],
            [row["point_Y"], row["wave_Y"]],
            color='yellow', linewidth=2, alpha=1,zorder=2
        )
        axins.scatter(row["point_X"],row["point_Y"],color='red', s=30, alpha=1, 
            edgecolors='red', marker='o', label='point',zorder=3)
        axins.scatter(row["wave_X"],row["wave_Y"],color='green',s=30, alpha=1, 
            edgecolors='green', marker='s', label='wave point',zorder=3)

        plt.axis("off")
        fig3.savefig(os.path.join(grandparent_folder,outputfigurefolder,f'plot_{k:0{num_digits}d}.png'), dpi=100, bbox_inches='tight')   
        #sys.exit()
        plt.close(fig3)

    k=k+1
        
    # do not show warning here
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        # savedata
        savetransect_wp = pd.concat([savetransect_wp, gpd.GeoDataFrame([row], crs=transect_wp.crs)], ignore_index=True)
        
savetransect_wp["Unique_ID"] = savetransect_wp["Unique_ID"].apply(
    lambda x: str(int(x)) if pd.notna(x) else ""
) 
savetransect_wp.set_crs(dem_bathy.crs, inplace=True)


savetransect_wp.to_file(os.path.join(grandparent_folder,outputfolder,outputfilename_gpkg), driver="GPKG")
savetransect_wp.to_file(os.path.join(grandparent_folder,outputfolder,outputfilename_shp), driver="ESRI Shapefile")
