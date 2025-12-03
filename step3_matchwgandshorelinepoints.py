#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 23 09:38:41 2025

@author: yshe948
"""
from tqdm import tqdm
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString
import os
import matplotlib.cm as cm
from scipy.spatial import cKDTree

# input
inputcoastlineloc = r"input\coastline"
inputshorelinepoints = r"input\shorelinepoints"
inputWGloc = r"input\wavedata\WGselected"
shorelinepointfilename = "JaMoNoRaSoWa"
wavedatafilename = f"wavedatasum_{shorelinepointfilename}_1979-01-01_2024-01-01.gpkg"
inputshorelinepointsfilename = f"lastestuniquepoints_{shorelinepointfilename}.gpkg"

num_nearst_WG = 4  # number of nearest wave points to get
extend_landward_m = 200  # meters to extend beyond start
extend_seaward_m = 2000  # meters to extend beyond end

# output
outputloc = r"output/match"
transect_wp_gpkg = f"transect_wp_{shorelinepointfilename}.gpkg"


# current folder
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder, outputloc), exist_ok=True)

# load coastal line
coastline = gpd.read_file(
    os.path.join(
        grandparent_folder, inputcoastlineloc, "nz-coastline-mean-high-water.shp"
    )
)

fig1, ax1 = plt.subplots(figsize=(12, 12))
coastline.plot(ax=ax1, color="blue", label="coastline")

# load shoreline point data
lastestuniquepoints = gpd.read_file(
    os.path.join(grandparent_folder, inputshorelinepoints, inputshorelinepointsfilename)
)


# load wavegauge location
gdf_WG = gpd.read_file(os.path.join(grandparent_folder, inputWGloc, wavedatafilename))

if coastline.crs != lastestuniquepoints.crs:
    coastline = coastline.to_crs(lastestuniquepoints.crs)

if gdf_WG.crs != lastestuniquepoints.crs:
    gdf_WG = coastline.to_crs(gdf_WG.crs)
print("coastline CRS:", coastline.crs)
print("shoreline points CRS:", lastestuniquepoints.crs)
print("WG CRS:", gdf_WG.crs)


def get_intersection_mindistnew(coastline, transectline):
    intersections = coastline.intersection(transectline)
    points = []

    if isinstance(intersections, gpd.GeoSeries):
        for geom in intersections:
            if geom.is_empty:
                continue
            if geom.geom_type == "Point":
                points.append(geom)
            elif geom.geom_type == "MultiPoint":
                points.extend(list(geom.geoms))
    else:
        if intersections.is_empty:
            pass
        elif intersections.geom_type == "Point":
            points.append(intersections)
        elif intersections.geom_type == "MultiPoint":
            points.extend(list(intersections.geoms))

    gdf_points = gpd.GeoDataFrame(geometry=points)
    gdf_points["x"] = gdf_points.geometry.x
    gdf_points["y"] = gdf_points.geometry.y
    return gdf_points


coords_tr = np.array(
    list(zip(lastestuniquepoints.geometry.x, lastestuniquepoints.geometry.y))
)
coords_wv = np.array(list(zip(gdf_WG.geometry.x, gdf_WG.geometry.y)))

tree = cKDTree(coords_wv)

distances, indices = tree.query(coords_tr, k=num_nearst_WG)

rows_intersection = []

# or i, (dist_row, idx_row) in enumerate(tqdm(zip(distances, indices), desc="Processing transects", ncols=80)):
for i, (dist_row, idx_row) in tqdm(
    enumerate(zip(distances, indices)),
    total=len(distances),  # <-- needed for percentage and ETA
    desc="Processing distances",  # label shown before the bar
    ncols=80,  # optional, sets display width
    unit="row",  # optional, shows “xx%|###| 100/500 [time] rows/s”
):
    ux1 = (
        lastestuniquepoints.loc[i, "ux1"]
        if "ux1" in lastestuniquepoints.columns
        else np.nan
    )
    uy1 = (
        lastestuniquepoints.loc[i, "uy1"]
        if "uy1" in lastestuniquepoints.columns
        else np.nan
    )
    Unique_ID = (
        lastestuniquepoints.loc[i, "Unique_ID"]
        if "Unique_ID" in lastestuniquepoints.columns
        else pd.nan
    )

    for dist, idx in zip(np.atleast_1d(dist_row), np.atleast_1d(idx_row)):
        # --- build a vector from transect to wave point
        x0, y0 = coords_tr[i]  # transect point
        x1, y1 = coords_wv[idx]  # wave point
        ux, uy = x1 - x0, y1 - y0
        length = np.hypot(ux, uy)
        if length == 0:
            continue
        ux, uy = ux / length, uy / length  # unit direction vector

        # --- extend landward (opposite direction)
        x2 = x0 - extend_landward_m * ux
        y2 = y0 - extend_landward_m * uy

        # --- full line from extended inland point to wave point
        line = LineString([(x2, y2), (x1, y1)])

        gdf_intersections = get_intersection_mindistnew(coastline, line)
        n_intersect = len(gdf_intersections)

        if n_intersect > 0:
            distances_to_intersections = np.sqrt(
                (gdf_intersections.geometry.x - x0) ** 2
                + (gdf_intersections.geometry.y - y0) ** 2
            )
            mean_dist_to_coast = distances_to_intersections.mean()
        else:
            mean_dist_to_coast = np.nan  # no intersection found

        CD_value = gdf_WG.iloc[idx]["CD"] if "CD" in gdf_WG.columns else np.nan

        rows_intersection.append(
            {
                "transect_id": i,
                "point_X": x0,
                "point_Y": y0,
                "ux1": ux1,
                "uy1": uy1,
                "Unique_ID": Unique_ID,
                "index_right": idx,  # wave id
                "wave_X": x1,
                "wave_Y": y1,
                "dist_m": dist,
                "n_intersections": n_intersect,
                "mean_dist_to_coast": mean_dist_to_coast,
                "CD": CD_value,
                "geometry": Point(x0, y0),
            }
        )


# convert to GeoDataFrame of lines
transect_wp_lines = gpd.GeoDataFrame(
    rows_intersection, geometry="geometry", crs=gdf_WG.crs
)
# del rows
transect_wp = (
    transect_wp_lines[
        (transect_wp_lines["n_intersections"] == 1)
        & (transect_wp_lines["mean_dist_to_coast"] < extend_landward_m)
    ]  # keep only intersection=1
    .sort_values(["point_X", "point_Y", "dist_m"])  # sort so smallest distance first
    .groupby(["point_X", "point_Y"], as_index=False)  # group by transect point
    .first()  # keep first (min dist)
)
transect_wp = gpd.GeoDataFrame(transect_wp, geometry="geometry", crs=gdf_WG.crs)
transect_wp.to_file(
    os.path.join(grandparent_folder, outputloc, transect_wp_gpkg), driver="GPKG"
)

unique_transect_wp_index_right = np.sort(transect_wp["index_right"].unique())


fig2, ax2 = plt.subplots(figsize=(60, 40))
n_c = len(unique_transect_wp_index_right)
colors = cm.rainbow(np.linspace(0, 1, n_c))
coastline.plot(ax=ax2, color="blue", label="coastline", linewidth=0.5, zorder=0)
for i, color in zip(unique_transect_wp_index_right, colors):
    subset = transect_wp[transect_wp["index_right"] == i]
    n_subset = len(subset)
    plt.scatter(
        transect_wp.loc[transect_wp["index_right"] == i, "point_X"],
        transect_wp.loc[transect_wp["index_right"] == i, "point_Y"],
        color=color,
        s=0.5,
        alpha=0.4,
        edgecolors=color,
        marker="o",
        zorder=1,  # label='points'
    )
    plt.scatter(
        transect_wp.loc[transect_wp["index_right"] == i, "wave_X"],
        transect_wp.loc[transect_wp["index_right"] == i, "wave_Y"],
        color=color,
        s=0.5,
        alpha=0.4,
        edgecolors=color,
        marker="s",
        label=f"Wave points {i:.0f}: ({n_subset:.0f})",
        zorder=2,
    )

    for _, row in subset.iterrows():
        ax2.plot(
            [row["point_X"], row["wave_X"]],
            [row["point_Y"], row["wave_Y"]],
            color=color,
            linewidth=0.1,
            alpha=0.1,
            zorder=3,
        )
    del row

ax2.set_title(
    f"{shorelinepointfilename} \n total: {len(lastestuniquepoints):.0f}; "
    f"match: {len(transect_wp):.0f}; "
    f"miss: {len(lastestuniquepoints)-len(transect_wp):.0f}",
    fontsize=25,
)
# plt.legend()
plt.axis("off")

fig2.savefig(
    os.path.join(
        grandparent_folder,
        outputloc,
        f"{shorelinepointfilename}_points_wavepoints_alignment.png",
    ),
    dpi=600,
    bbox_inches="tight",
)
