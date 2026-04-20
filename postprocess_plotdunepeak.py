#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  7 08:53:45 2025

@author: yshe948
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import os

inputloc = r"output/dunepeak"
outputloc = r"output/dunepeak"

buffer_dist = 5  # unit m
inputfilename = "dunepeak_pct1_fw10_bw50_s5.gpkg"
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
outputfigname = "dunepeak_pct1_fw10_bw50_s5.png"

dunepeak = gpd.read_file(os.path.join(grandparent_folder, inputloc, inputfilename))
# sys.exit()
var = "coast_elev_m"
# Cap values greater than 10
dunepeak[var] = dunepeak[var].clip(lower=0, upper=10)

fig, ax = plt.subplots(figsize=(8, 6))
im = dunepeak.plot(
    column=var,
    ax=ax,
    legend=True,
    cmap="jet",
    markersize=40,
    edgecolor="none",
    linewidth=0.3,
)
cbar = im.get_figure().axes[-1]  # colourbar axis is the last axis
cbar.set_ylabel("Elevation (m)", fontsize=10)
mean_var = dunepeak[var].mean()
std_var = dunepeak[var].std()
ax.set_title(
    f"buffer={buffer_dist} m \n dunepeak={mean_var:.1f}±{std_var:.1f} m",
    fontsize=10,
)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_aspect("equal")
ax.set_xlim([5.6 * 10**6, 6.7 * 10**6])
ax.set_ylim([-4.6 * 10**6, -3 * 10**6])
plt.tight_layout()
plt.show()

fig.savefig(
    os.path.join(grandparent_folder, outputloc, outputfigname),
    dpi=300,
    bbox_inches="tight",
)
