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

shorelinepointfilename = "JaMoNoRaSoWa"
inputfolderloc = r"output/brunnrule"
outputfolderloc = r"output/brunnrule"
buffer_dist = 10

inputfilename = f"brunnrule_{shorelinepointfilename}_buffer_{buffer_dist}.gpkg"
inputcoastlinefolder = "input/coastline"
inputcoastlinefile = "nz-coastline-mean-high-water.shp"
outputfig1 = f"tanb_{shorelinepointfilename}_buffer_{buffer_dist}.png"

# current folder
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))

data = gpd.read_file(os.path.join(grandparent_folder, inputfolderloc, inputfilename))


figh = 8
figw = 6
markersizeplot = 40
fz = 10
colormapplot = "jet"


## log
fig1, ax1 = plt.subplots(figsize=(figh, figw))

# Apply logarithmic normalisation
norm = colors.LogNorm(vmin=data["tanbeta"].min(), vmax=data["tanbeta"].max())

im = data.plot(
    column="tanbeta",
    cmap=colormapplot,
    legend=False,
    markersize=markersizeplot,
    ax=ax1,
    norm=norm,  # apply the log scale
)

tanbeta_mean = data["tanbeta"].mean()
tanbeta_std = data["tanbeta"].std()

# Add colourbar manually with the same norm
sm1 = plt.cm.ScalarMappable(cmap=colormapplot, norm=norm)
sm1._A = []  # compatibility for older matplotlib versions
cbar = fig1.colorbar(sm1, ax=ax1)
cbar.set_label(r"$\tan(\beta)$", fontsize=fz)

# Title and labels
ax1.set_title(
    f"{shorelinepointfilename}_buffer_{buffer_dist}: \n mean: {tanbeta_mean:.2f}; std: {tanbeta_std:.2f}"
)
ax1.set_xlabel("x (m)")
ax1.set_ylabel("y (m)")
plt.tight_layout()
plt.show()


fig1.savefig(
    os.path.join(grandparent_folder, outputfolderloc, outputfig1),
    dpi=600,
    bbox_inches="tight",
)
