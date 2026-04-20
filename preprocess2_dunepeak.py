#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 25 22:39:36 2025

@author: yshe948
"""

from tqdm import tqdm
import geopandas as gpd
import numpy as np
import rasterio as rio
from rasterio.mask import mask
import matplotlib.pyplot as plt
import os
import math
# shapely is used for constructing directional buffer geometries
from shapely.geometry import Point, Polygon
from shapely import affinity

# input shoreline points directory; choose first gpkg found
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
inputshorelinepoints = os.path.join(base_dir, "input/shorelinepoints")
bathyname = r"nzbathy_2016.tif"
preferred_file = "latestuniquepoints_merged.gpkg"
preferred_path = os.path.join(inputshorelinepoints, preferred_file)
if not os.path.exists(preferred_path):
    raise FileNotFoundError(
        f"required shoreline file not found: {preferred_file} in {inputshorelinepoints}"
    )
inputshorelinepointsfilename = preferred_file
# buffer parameters used for elevation sampling
# original circular buffer gave too much weight to seaward/sideward
# directions.  we construct an anisotropic, oriented zone that
# extends a little bit seaward, a bit either side, and a lot
# landward along the local shore normal.  the geometry is built from
# a rectangle with semicircular end‑caps.
# all distances in metres
forward_dist = 5    # how far to look seaward (small)
backward_dist = 20   # how far to look landward (large)
side_dist = 5        # lateral extent either side alongshore

# statistic for crest estimation.  we only use the percentile
# method – average the highest `top_fraction` of raster cells within the
# buffer.  extra methods were previously experimented with but proved
# unreliable, so they have been removed.

# proportion of the buffer cells to include when calculating the crest.
# 0.05 means the top 5 % of the elevations in the buffer, 0.01 means the top 1 %, etc.
top_fraction = 0.05  # portion of the top elevations to average (0-1)
# summary measure for the selected subset – mean (default) or median.
# median is less influenced by an isolated high pixel such as a bush.
top_statistic = 'mean'  # 'mean' or 'median'

# parameters for profile‑based methods
profile_step = 5      # metres between samples when scanning along normal
# when using the 'first' method ignore any maxima within this distance of
# the sample point (typically equal to forward_dist).  this prevents
# picking up a single noisy pixel seaward of the toe or a very small
# vegetated bump. set to 0 to allow peaks right next to the point.
min_peak_dist = forward_dist

# gap-aware tangent setting: if consecutive points are farther apart than
# this threshold, treat them as different shoreline segments for orientation.
# Tangent estimation works best with two nearby neighbors (previous + next),
# can still operate with one nearby neighbor, and falls back to a neutral
# axis when neither side has a nearby neighbor.
alongshore_gap_threshold_m = 15


outputloc = r"output/dunepeak"
# include the directional parameters in output names
# plus the percentile fraction for clarity
outputfilename = (
    f"dunepeak_pct{int(top_fraction*100)}_fw{forward_dist}_bw{backward_dist}"
    f"_s{side_dist}.gpkg"
)
outputfigname = (
    f"dunepeak_pct{int(top_fraction*100)}_fw{forward_dist}_bw{backward_dist}"
    f"_s{side_dist}.png"
)
# currentlocation
current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))
os.makedirs(os.path.join(grandparent_folder, outputloc), exist_ok=True)
coastfolderloc = os.path.join(grandparent_folder, "input/CoastalLiDAR")
bathyfolderloc = os.path.join(grandparent_folder, "input/Bathymetry250m")

# load shoreline point data
lastestuniquepoints = gpd.read_file(
    os.path.join(grandparent_folder, inputshorelinepoints, inputshorelinepointsfilename)
)
print("shoreline points CRS:", lastestuniquepoints.crs)

coast_DEM = os.path.join(coastfolderloc, "NewZealand_Coastal_DEM_Merged_250m.tif")

coast_elev = np.full(len(lastestuniquepoints), np.nan)  # initialise all NaN
# coast_source = np.full(len(lastestuniquepoints), None, dtype=object)

with rio.open(coast_DEM) as src:
    # Reproject buffer to DEM CRS if needed

    if lastestuniquepoints.crs != src.crs:
        lastestuniquepoints = lastestuniquepoints.to_crs(src.crs)

    left, bottom, right, top = src.bounds

    # precompute shore‑tangent vectors for every point using gap-aware
    # neighbors. Consecutive rows farther apart than
    # `alongshore_gap_threshold_m` are treated as segment breaks so that
    # cross-beach jumps do not influence local normals.
    coords = np.array([[pt.x, pt.y] for pt in lastestuniquepoints.geometry])
    npts = len(coords)
    tangents = np.zeros_like(coords)

    if npts > 1:
        seg_vec = coords[1:] - coords[:-1]
        seg_dist = np.linalg.norm(seg_vec, axis=1)

        prev_vec = np.zeros_like(coords)
        prev_vec[1:] = seg_vec
        next_vec = np.zeros_like(coords)
        next_vec[:-1] = seg_vec

        prev_valid = np.zeros(npts, dtype=bool)
        prev_valid[1:] = seg_dist <= alongshore_gap_threshold_m
        next_valid = np.zeros(npts, dtype=bool)
        next_valid[:-1] = seg_dist <= alongshore_gap_threshold_m

        both_valid = prev_valid & next_valid
        only_prev = prev_valid & ~next_valid
        only_next = next_valid & ~prev_valid

        tangents[both_valid] = prev_vec[both_valid] + next_vec[both_valid]
        tangents[only_prev] = prev_vec[only_prev]
        tangents[only_next] = next_vec[only_next]

    # if tangent is still zero (isolated point), use a neutral fallback;
    # the inland/seaward flip test below still selects the better side.
    zero_mask = np.linalg.norm(tangents, axis=1) == 0
    tangents[zero_mask] = np.array([1.0, 0.0])

    # Loop through points that are still NaN
    for i, geom in tqdm(
        enumerate(lastestuniquepoints.geometry),
        total=len(lastestuniquepoints),
        desc="Processing points",
    ):
        # Skip if already found a value
        if not np.isnan(coast_elev[i]):
            continue

        # Skip if point outside DEM extent
        if not (left <= geom.x <= right and bottom <= geom.y <= top):
            continue

        # Try sampling from this DEM
        try:
            # construct a directional sampling polygon aligned with
            # the local shore normal.  a small `forward_dist` limits
            # sampling in the seaward direction, while a large
            # `backward_dist` reaches into the dune system.  `side_dist`
            # controls the width alongshore.  The shape is a rectangle
            # capped with semicircles for smoothness.

            # determine unit normal vector from precomputed tangent.  The
            # tangent vector `t` points roughly alongshore, so a 90°
            # rotation gives a vector perpendicular to the coast.  There are
            # two possible normals (left/right of the tangent) – one will
            # point landward, the other seaward.  A 180° rotation would just
            # flip the alongshore direction and is not relevant here.
            t = tangents[i]
            if np.linalg.norm(t) == 0:
                t = np.array([1.0, 0.0])

            # initial normal (90° rotation clockwise)
            normal = np.array([t[1], -t[0]])

            # use local DEM sampling to decide which normal points inland.
            # sample a few points along both `normal` and `-normal` and take
            # the mean elevation; the landward direction should have higher
            # values (dune vs sea).  this automatically handles islands and
            # weird coast orientations without needing an external polygon.
            try:
                def mean_along(direction):
                    vals = []
                    step = 10  # metres between samples
                    nsteps = 5  # how many hops
                    for k in range(1, nsteps + 1):
                        dx, dy = direction * (k * step)
                        sx, sy = geom.x + dx, geom.y + dy
                        if left <= sx <= right and bottom <= sy <= top:
                            v = list(src.sample([(sx, sy)]))[0][0]
                            if not np.isnan(v) and v < 1000:
                                vals.append(v)
                    return np.nanmean(vals) if vals else np.nan

                mean_norm = mean_along(normal)
                mean_flip = mean_along(-normal)
                # if the flipped direction has larger mean elevation, switch
                if not np.isnan(mean_flip) and (
                    np.isnan(mean_norm) or mean_flip > mean_norm
                ):
                    normal = -normal
            except Exception:
                # if sampling fails for any reason, fall back to the
                # previously hard‑coded orientation (normal = [t[1], -t[0]])
                pass


            # local (normal/alongshore) buffer geometry
            rect = Polygon([
                (-forward_dist, -side_dist),
                (-forward_dist, side_dist),
                (backward_dist, side_dist),
                (backward_dist, -side_dist),
            ])
            cap_seaward = Point(-forward_dist, 0).buffer(side_dist, resolution=16)
            cap_landward = Point(backward_dist, 0).buffer(side_dist, resolution=16)
            buf_local = rect.union(cap_seaward).union(cap_landward)

            # rotate/translate into map coordinates
            angle = math.degrees(math.atan2(normal[1], normal[0]))
            buf_rot = affinity.rotate(buf_local, angle, origin=(0, 0))
            geom_buffer = affinity.translate(buf_rot, geom.x, geom.y)

            # crop DEM within the oriented buffer polygon; we always
            # grab this block because the percentile method still needs
            # it, and it provides a fallback for the profile techniques.
            out_image, _ = mask(src, [geom_buffer], crop=True, filled=False)
            data = out_image[0].astype(float)
            if np.ma.isMaskedArray(data):
                data = data.filled(np.nan)

            if src.nodata is not None:
                data[data == src.nodata] = np.nan

            # Remove invalid/sentinel values from statistics
            data[(data <= -9990) | (data > 1000)] = np.nan
            data = data[np.isfinite(data)]

            # compute percentile-based crest value (the only method now)
            if data.size == 0:
                val = math.nan
            else:
                n = max(1, int(np.ceil(data.size * top_fraction)))
                top_vals = np.sort(data)[-n:]
                if top_statistic == 'median':
                    val = np.nanmedian(top_vals)
                else:
                    val = np.nanmean(top_vals)
            
            if not np.isnan(val):
                coast_elev[i] = val
        except Exception:
            continue  # skip invalid or out-of-bounds sample
lastestuniquepoints["coast_elev_m"] = coast_elev
# lastestuniquepoints["source_DEM"] = coast_source

# === Open DEM ===
bathy_path = os.path.join(bathyfolderloc, bathyname)

with rio.open(bathy_path) as src:
    # Reproject shoreline points if needed
    if lastestuniquepoints.crs != src.crs:
        lastestuniquepoints = lastestuniquepoints.to_crs(src.crs)
        print(f"Reprojected shoreline points to match DEM CRS: {src.crs}")

    # Prepare list for peak elevation values
    peak_elev_values = []

    # Loop through each shoreline point
    for geom in tqdm(
        lastestuniquepoints.geometry, desc="Sampling DEM values from bathy"
    ):
        try:
            val = list(src.sample([(geom.x, geom.y)]))[0][0]
            peak_val = val
        except Exception:
            peak_val = np.nan

        peak_elev_values.append(peak_val)

# === Add shoreline-point DEM value to GeoDataFrame ===
lastestuniquepoints["shoreline_elev_m"] = peak_elev_values


# savedata
lastestuniquepoints.to_file(
    os.path.join(grandparent_folder, outputloc, outputfilename), driver="gpkg"
)

var = "coast_elev_m"
# Don't cap visualization – show actual range
vmin = lastestuniquepoints[var].quantile(0.02)
vmax = lastestuniquepoints[var].quantile(0.98)

fig, ax = plt.subplots(figsize=(8, 6))
im = lastestuniquepoints.plot(
    column=var,
    ax=ax,
    vmin=vmin,
    vmax=vmax,
    legend=True,
    cmap="viridis",
    markersize=40,
    edgecolor="k",
    linewidth=0.3,
)
cbar = im.get_figure().axes[-1]  # colourbar axis is the last axis
cbar.set_ylabel("Height (m)", fontsize=10)
mean_var = lastestuniquepoints[var].mean()
std_var = lastestuniquepoints[var].std()
ax.set_title(
    f"percentile={int(top_fraction*100)}%, forward={forward_dist} m, backward={backward_dist} m, side={side_dist} m"
    f"side={side_dist} m \n dunepeak={mean_var:.1f}±{std_var:.1f} m",
    fontsize=10,
)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_aspect("equal")
plt.tight_layout()
plt.show()

fig.savefig(
    os.path.join(grandparent_folder, outputloc, outputfigname),
    dpi=300,
    bbox_inches="tight",
)
