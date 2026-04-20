#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov  5 08:38:17 2025

@author: useradmin-yshe948
"""
import os
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as colors

inputfolderloc = r"output/bruunrule"
buffer_dist = 5
confidence_level = "medium_confidence"
year = 2150
percentile = 0.5
scenario = 4.5
outputfolderloc = r"output/bruunrule"

inputfilename = f"bruunrule_b_{buffer_dist}_{confidence_level}_y_{year}_s_{scenario}_p_{percentile}.gpkg"
outputfig1 = f"ER_b_{buffer_dist}_{confidence_level}_y_{year}_s_{scenario}_p_{percentile}.png"
outputfig2 = f"E_b_{buffer_dist}_{confidence_level}_y_{year}_s_{scenario}_p_{percentile}.png"
inputcoastlinefolder = "input/coastline"
inputcoastlinefile = "nz-coastline-mean-high-water.shp"

# current folder
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))

input_path = os.path.join(grandparent_folder, inputfolderloc, inputfilename)
if os.path.exists(input_path):
    data = gpd.read_file(input_path)
else:
    folder = os.path.join(grandparent_folder, inputfolderloc)
    gpkg_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith(".gpkg") and f.startswith("bruunrule")
    ]
    data = None
    for candidate in gpkg_files:
        candidate_data = gpd.read_file(candidate)
        if {"ER_SLR", "R_SLR"}.issubset(candidate_data.columns):
            data = candidate_data
            input_path = candidate
            break
    if data is None:
        raise FileNotFoundError(
            "No bruunrule SLR output with ER_SLR/R_SLR found. Run step5_addSLR.py first."
        )

figh = 8
figw = 6
markersizeplot = 40
fz = 10
colormapplot = "jet"

## log colorbar

fig1, ax1 = plt.subplots(figsize=(figh, figw))

# Apply logarithmic normalisation
norm = colors.LogNorm(vmin=data["ER_SLR"].min(), vmax=data["ER_SLR"].max())

im = data.plot(
    column="ER_SLR",
    cmap=colormapplot,
    legend=False,
    markersize=markersizeplot,
    ax=ax1,
    norm=norm,  # apply the log scale
)

tanbeta_mean = data["ER_SLR"].mean()
tanbeta_std = data["ER_SLR"].std()

# Add colourbar manually with the same norm
sm1 = plt.cm.ScalarMappable(cmap=colormapplot, norm=norm)
sm1._A = []  # compatibility for older matplotlib versions
cbar = fig1.colorbar(sm1, ax=ax1)
cbar.set_label("ER (m/yr)", fontsize=fz)

# Title and labels
ax1.set_title(
    f"b_{buffer_dist} \n {confidence_level}_y_{year}_s_{scenario}_p_{percentile}"
)
ax1.set_xlabel("x (m)")
ax1.set_ylabel("y (m)")
plt.tight_layout()
plt.show()


fig2, ax2 = plt.subplots(figsize=(figh, figw))

# Apply logarithmic normalization
norm2 = colors.LogNorm(vmin=data["R_SLR"].min(), vmax=data["R_SLR"].max())

im = data.plot(
    column="R_SLR",
    cmap=colormapplot,
    legend=False,
    markersize=markersizeplot,
    ax=ax2,
    norm=norm2,
)

beta_rad_mean = data["R_SLR"].mean()
beta_rad_std = data["R_SLR"].std()

# Add colourbar manually
sm2 = plt.cm.ScalarMappable(cmap=colormapplot, norm=norm2)
sm2._A = []  # compatibility for older matplotlib versions
cbar = fig2.colorbar(sm2, ax=ax2)
cbar.set_label("R (m)", fontsize=fz)
# title and labels
ax2.set_title(
    f"b_{buffer_dist} \n {confidence_level}_y_{year}_s_{scenario}_p_{percentile}"
)
ax2.set_xlabel("x (m)")
ax2.set_ylabel("y (m)")
plt.tight_layout()
plt.show()

# sys.exit()

## linear colorbar

# fig1,ax1= plt.subplots(figsize=(figh, figw))
# im=data.plot(
#     column="ER_SLR",              # which column to colour by
#     cmap=colormapplot,           # colour map
#     legend=False,             # disable built-in legend
#     markersize=markersizeplot,
#     ax=ax1
# )
# # add colourbar manually
# sm1 = plt.cm.ScalarMappable(
#     cmap=colormapplot,
#     norm=plt.Normalize(vmin=data["ER_SLR"].min(), vmax=data["ER_SLR"].max())
# )
# sm1._A = []  # needed for older matplotlib versions
# cbar = fig1.colorbar(sm1, ax=ax1)
# cbar.set_label("ER (m/yr)", fontsize=fz)
# # title and labels
# ax1.set_title(f"{shorelinepointfilename}_b_{buffer_dist}: {confidence_level}_y_{year}_s_{scenario}_p_{percentile}")
# ax1.set_xlabel("x (m)")
# ax1.set_ylabel("y (m)")
# plt.tight_layout()
# plt.show()

# fig2,ax2= plt.subplots(figsize=(figh, figw))
# im=data.plot(
#     column="R_SLR",              # which column to colour by
#     cmap=colormapplot,           # colour map
#     legend=False,             # disable built-in legend
#     markersize=markersizeplot,
#     ax=ax2
# )
# # add colourbar manually
# sm2 = plt.cm.ScalarMappable(
#     cmap=colormapplot,
#     norm=plt.Normalize(vmin=data["R_SLR"].min(), vmax=data["R_SLR"].max())
# )
# sm2._A = []  # needed for older matplotlib versions
# cbar = fig1.colorbar(sm2, ax=ax2)
# cbar.set_label("R (m)", fontsize=fz)
# # title and labels
# ax2.set_title(f"{shorelinepointfilename}_b_{buffer_dist}: {confidence_level}_y_{year}_s_{scenario}_p_{percentile}")
# ax2.set_xlabel("x (m)")
# ax2.set_ylabel("y (m)")
# plt.tight_layout()
# plt.show()

fig1.savefig(
    os.path.join(grandparent_folder, outputfolderloc, outputfig1),
    dpi=600,
    bbox_inches="tight",
)
fig2.savefig(
    os.path.join(grandparent_folder, outputfolderloc, outputfig2),
    dpi=600,
    bbox_inches="tight",
)
