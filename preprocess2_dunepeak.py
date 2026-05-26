#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 25 22:39:36 2025

@author: yshe948
"""

from tqdm import tqdm
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio as rio
import matplotlib.pyplot as plt
import os
import glob
from depthofclosure_settings import CD_METHOD, B_SOURCE

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

print(f"CD_METHOD={CD_METHOD}  B_SOURCE={B_SOURCE}")

# Dune-crest extraction parameters (1 m DEM workflow)
MAX_POINT_GAP_M = 10.0  # do not connect shoreline points across larger gaps
ORIENT_PROBE_MAX_M = 25.0  # left/right probe length from shoreline point
ORIENT_PROBE_STEP_M = 2.0
PROFILE_START_M = 2.0
PROFILE_MAX_M = 80.0  # landward search distance for dune crest
PROFILE_STEP_M = 1.0
SMOOTH_WINDOW = 5  # moving-average window in samples (1 m spacing)
MIN_RISE_M = 0.35  # minimum rise above local low before accepting crest
CREST_AVG_SIDE_POINTS = 5  # average 5 points each side of detected crest (10-point mean)
FLAT_TOL_M = 0.03  # treat elevations within 3 cm as a flat crest plateau
POST_CREST_CHECK_POINTS = 6  # require no further rise over next ~6 m

outputloc = r"output/dunepeak"
outputfilename = "shoretoe_elev_combined.gpkg"
outputfigname = "shoretoe_elev_combined.png"
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

# Prefer a 1 m DEM when available; otherwise fall back to merged 250 m file.
coast_dem_candidates = sorted(glob.glob(os.path.join(coastfolderloc, "*1m*.tif")))
if coast_dem_candidates:
    coast_DEM = coast_dem_candidates[0]
else:
    coast_DEM = os.path.join(coastfolderloc, "NewZealand_Coastal_DEM_Merged_250m.tif")

print(f"Using coastal DEM: {coast_DEM}")


def moving_average(values, window):
    if window <= 1 or len(values) == 0:
        return values
    return (
        pd.Series(values)
        .rolling(window=window, center=True, min_periods=1)
        .mean()
        .to_numpy()
    )


def sample_dem_point(src, x, y):
    left, bottom, right, top = src.bounds
    if not (left <= x <= right and bottom <= y <= top):
        return np.nan
    try:
        val = list(src.sample([(x, y)]))[0][0]
    except Exception:
        return np.nan

    if src.nodata is not None and val == src.nodata:
        return np.nan
    if not np.isfinite(val) or val <= -9990 or val > 1000:
        return np.nan
    return float(val)


def sample_dem_profile(src, x0, y0, ux, uy, distances):
    coords = [(x0 + ux * d, y0 + uy * d) for d in distances]
    left, bottom, right, top = src.bounds
    values = np.full(len(coords), np.nan)

    for i, (x, y) in enumerate(coords):
        if not (left <= x <= right and bottom <= y <= top):
            continue
        try:
            val = list(src.sample([(x, y)]))[0][0]
            if src.nodata is not None and val == src.nodata:
                continue
            if not np.isfinite(val) or val <= -9990 or val > 1000:
                continue
            values[i] = float(val)
        except Exception:
            continue
    return values


def first_local_peak(distances, profile, min_rise_m):
    smoothed = moving_average(profile, SMOOTH_WINDOW)
    if np.isfinite(smoothed).sum() < 3:
        return np.nan, np.nan, None, smoothed

    n = len(smoothed)

    for i in range(1, n - 1):
        z_prev, z_now, z_next = smoothed[i - 1], smoothed[i], smoothed[i + 1]
        if not (np.isfinite(z_now) and np.isfinite(z_prev) and np.isfinite(z_next)):
            continue

        running_min = np.nanmin(smoothed[: i + 1])
        if not np.isfinite(running_min) or (z_now - running_min) < min_rise_m:
            continue

        # Candidate must be at/near a local top, allowing a flat plateau.
        if (z_now + FLAT_TOL_M) < z_prev or (z_now + FLAT_TOL_M) < z_next:
            continue

        # If profile is still rising in the next few meters, this is not the crest yet.
        look_end = min(n, i + 1 + POST_CREST_CHECK_POINTS)
        post = smoothed[i + 1 : look_end]
        post = post[np.isfinite(post)]
        if post.size > 0 and np.nanmax(post) > (z_now + FLAT_TOL_M):
            continue

        # Expand around i to capture flat-top crest and use center index.
        left = i
        right = i
        while left - 1 >= 0 and np.isfinite(smoothed[left - 1]) and abs(smoothed[left - 1] - z_now) <= FLAT_TOL_M:
            left -= 1
        while right + 1 < n and np.isfinite(smoothed[right + 1]) and abs(smoothed[right + 1] - z_now) <= FLAT_TOL_M:
            right += 1
        peak_idx = (left + right) // 2
        return float(smoothed[peak_idx]), float(distances[peak_idx]), peak_idx, smoothed

    if np.isfinite(smoothed).any():
        peak_idx = int(np.nanargmax(smoothed))
        return float(smoothed[peak_idx]), float(distances[peak_idx]), peak_idx, smoothed
    return np.nan, np.nan, None, smoothed


def average_around_peak(smoothed_profile, peak_idx, side_points):
    if peak_idx is None or len(smoothed_profile) == 0:
        return np.nan

    left_idx = list(range(max(0, peak_idx - side_points), peak_idx))
    right_idx = list(range(peak_idx + 1, min(len(smoothed_profile), peak_idx + 1 + side_points)))
    idx = left_idx + right_idx

    vals = smoothed_profile[idx] if idx else np.array([])
    vals = vals[np.isfinite(vals)]

    # Near segment boundaries there may be fewer than 10 side points; include crest as fallback.
    if vals.size < max(4, side_points):
        i0 = max(0, peak_idx - side_points)
        i1 = min(len(smoothed_profile), peak_idx + side_points + 1)
        vals = smoothed_profile[i0:i1]
        vals = vals[np.isfinite(vals)]

    if vals.size == 0:
        return np.nan
    return float(np.nanmean(vals))


def compute_segment_ids(gdf, max_gap_m):
    if "Unique_ID" in gdf.columns:
        order = pd.to_numeric(gdf["Unique_ID"], errors="coerce").sort_values().index
        work = gdf.loc[order].copy()
    else:
        work = gdf.copy()

    work["point_X"] = work.geometry.x
    work["point_Y"] = work.geometry.y
    dx = work["point_X"].diff()
    dy = work["point_Y"].diff()
    gap = np.hypot(dx, dy)
    new_segment = gap.isna() | (gap > max_gap_m)
    work["segment_id"] = new_segment.cumsum().astype(int)
    return work

# Build contiguous shoreline segments (do not connect points across >10 m gaps).
lastestuniquepoints = compute_segment_ids(lastestuniquepoints, MAX_POINT_GAP_M)

# Extract dune crest from coastal DEM using left/right seaward inference.
coast_elev = np.full(len(lastestuniquepoints), np.nan)
crest_dist_m = np.full(len(lastestuniquepoints), np.nan)
seaward_side = np.full(len(lastestuniquepoints), "unknown", dtype=object)
crest_peak_m = np.full(len(lastestuniquepoints), np.nan)
crest_avg10_m = np.full(len(lastestuniquepoints), np.nan)

with rio.open(coast_DEM) as src:
    if lastestuniquepoints.crs != src.crs:
        lastestuniquepoints = lastestuniquepoints.to_crs(src.crs)
        lastestuniquepoints["point_X"] = lastestuniquepoints.geometry.x
        lastestuniquepoints["point_Y"] = lastestuniquepoints.geometry.y

    for i in tqdm(
        range(len(lastestuniquepoints)),
        total=len(lastestuniquepoints),
        desc="Finding dune crest from coastal DEM",
    ):
        row = lastestuniquepoints.iloc[i]
        x0, y0 = row.geometry.x, row.geometry.y
        seg_id = row["segment_id"]

        z0 = sample_dem_point(src, x0, y0)

        has_prev = i > 0 and lastestuniquepoints.iloc[i - 1]["segment_id"] == seg_id
        has_next = i < len(lastestuniquepoints) - 1 and lastestuniquepoints.iloc[i + 1]["segment_id"] == seg_id

        if has_prev and has_next:
            p_prev = lastestuniquepoints.iloc[i - 1].geometry
            p_next = lastestuniquepoints.iloc[i + 1].geometry
            tx, ty = p_next.x - p_prev.x, p_next.y - p_prev.y
        elif has_prev:
            p_prev = lastestuniquepoints.iloc[i - 1].geometry
            tx, ty = x0 - p_prev.x, y0 - p_prev.y
        elif has_next:
            p_next = lastestuniquepoints.iloc[i + 1].geometry
            tx, ty = p_next.x - x0, p_next.y - y0
        else:
            coast_elev[i] = z0
            seaward_side[i] = "unknown"
            continue

        tlen = np.hypot(tx, ty)
        if tlen == 0:
            coast_elev[i] = z0
            seaward_side[i] = "unknown"
            continue

        tx /= tlen
        ty /= tlen
        nx_left, ny_left = -ty, tx
        nx_right, ny_right = ty, -tx

        probe_dist = np.arange(
            ORIENT_PROBE_STEP_M, ORIENT_PROBE_MAX_M + ORIENT_PROBE_STEP_M, ORIENT_PROBE_STEP_M
        )
        z_left = sample_dem_profile(src, x0, y0, nx_left, ny_left, probe_dist)
        z_right = sample_dem_profile(src, x0, y0, nx_right, ny_right, probe_dist)
        left_mean = np.nanmean(z_left)
        right_mean = np.nanmean(z_right)

        if np.isfinite(left_mean) and np.isfinite(right_mean):
            if left_mean < right_mean:
                seaward_side[i] = "left"
                ux_land, uy_land = nx_right, ny_right
            else:
                seaward_side[i] = "right"
                ux_land, uy_land = nx_left, ny_left
        elif np.isfinite(left_mean):
            seaward_side[i] = "right_unknown"
            ux_land, uy_land = nx_left, ny_left
        elif np.isfinite(right_mean):
            seaward_side[i] = "left_unknown"
            ux_land, uy_land = nx_right, ny_right
        else:
            coast_elev[i] = z0
            seaward_side[i] = "unknown"
            continue

        profile_dist = np.arange(PROFILE_START_M, PROFILE_MAX_M + PROFILE_STEP_M, PROFILE_STEP_M)
        z_profile = sample_dem_profile(src, x0, y0, ux_land, uy_land, profile_dist)
        z_peak, d_peak, peak_idx, z_smoothed = first_local_peak(profile_dist, z_profile, MIN_RISE_M)
        z_avg10 = average_around_peak(z_smoothed, peak_idx, CREST_AVG_SIDE_POINTS)

        if np.isfinite(z_peak):
            coast_elev[i] = z_avg10 if np.isfinite(z_avg10) else z_peak
            crest_dist_m[i] = d_peak
            crest_peak_m[i] = z_peak
            crest_avg10_m[i] = z_avg10
        else:
            coast_elev[i] = z0
            crest_dist_m[i] = np.nan
            crest_peak_m[i] = np.nan
            crest_avg10_m[i] = np.nan

lastestuniquepoints["coast_elev_m"] = coast_elev
lastestuniquepoints["dune_crest_dist_m"] = crest_dist_m
lastestuniquepoints["seaward_side"] = seaward_side
lastestuniquepoints["dune_crest_peak_m"] = crest_peak_m
lastestuniquepoints["dune_crest_avg10_m"] = crest_avg10_m
lastestuniquepoints = lastestuniquepoints.sort_index()

# === Open DEM for bathymetry elevation at shoreline XY ===
bathy_path = os.path.join(bathyfolderloc, bathyname)

with rio.open(bathy_path) as src:
    if lastestuniquepoints.crs != src.crs:
        lastestuniquepoints = lastestuniquepoints.to_crs(src.crs)
        print(f"Reprojected shoreline points to match DEM CRS: {src.crs}")

    peak_elev_values = []
    for geom in tqdm(
        lastestuniquepoints.geometry, desc="Sampling DEM values from bathy"
    ):
        try:
            val = list(src.sample([(geom.x, geom.y)]))[0][0]
            peak_val = val
        except Exception:
            peak_val = np.nan
        peak_elev_values.append(peak_val)

lastestuniquepoints["shoreline_elev_m"] = peak_elev_values

# === Source B (dune/berm height) based on B_SOURCE setting ===
# === Always compute both B columns so output GPKG works with any CD_METHOD ===
# B_mhws_elev_m: coastal LiDAR elevation at MHWS XY (for hallermeier_outer / birkemeier_1985)
# coast_elev_m:  coastal LiDAR elevation at shoreline XY (for hallermeier_inner)
proxy_parquet = os.path.join(base_dir, "code", "nzccd_rates_proxy.parquet")
if not os.path.exists(proxy_parquet):
    print(
        f"WARNING: nzccd_rates_proxy.parquet not found at {proxy_parquet}. "
        "B_mhws_elev_m will be NaN. Required for hallermeier_outer / birkemeier_1985."
    )
    lastestuniquepoints["B_mhws_elev_m"] = np.nan
    lastestuniquepoints["mhws_x"] = np.nan
    lastestuniquepoints["mhws_y"] = np.nan
else:
    proxy = gpd.read_parquet(proxy_parquet)[["UniqueID", "geometry"]].copy()
    proxy = proxy.to_crs(lastestuniquepoints.crs)
    proxy["mhws_x"] = proxy.geometry.x
    proxy["mhws_y"] = proxy.geometry.y

    mhws_elev = np.full(len(proxy), np.nan)
    with rio.open(coast_DEM) as src:
        if proxy.crs != src.crs:
            proxy = proxy.to_crs(src.crs)
        left, bottom, right, top = src.bounds
        for i, geom in tqdm(
            enumerate(proxy.geometry),
            total=len(proxy),
            desc="Sampling coastal LiDAR at MHWS points",
        ):
            if not (left <= geom.x <= right and bottom <= geom.y <= top):
                continue
            try:
                val = list(src.sample([(geom.x, geom.y)]))[0][0]
                if src.nodata is not None and val == src.nodata:
                    val = np.nan
                if not np.isfinite(val) or val <= -9990 or val > 1000:
                    val = np.nan
                mhws_elev[i] = val
            except Exception:
                continue
    proxy["B_mhws_elev_m"] = mhws_elev

    proxy["UniqueID_norm"] = (
        pd.to_numeric(proxy["UniqueID"], errors="coerce").astype("Int64").astype(str)
    )
    lastestuniquepoints["UniqueID_norm"] = (
        pd.to_numeric(lastestuniquepoints["Unique_ID"], errors="coerce").astype("Int64").astype(str)
    )
    lastestuniquepoints = lastestuniquepoints.merge(
        proxy[["UniqueID_norm", "B_mhws_elev_m", "mhws_x", "mhws_y"]],
        on="UniqueID_norm",
        how="left",
    ).drop(columns=["UniqueID_norm"])
    print(
        f"MHWS elevation joined: "
        f"{lastestuniquepoints['B_mhws_elev_m'].notna().sum()} / {len(lastestuniquepoints)} points"
    )


# savedata
lastestuniquepoints.to_file(
    os.path.join(grandparent_folder, outputloc, outputfilename), driver="gpkg"
)

var = "coast_elev_m"
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
cbar = im.get_figure().axes[-1]
cbar.set_ylabel("Height (m)", fontsize=10)
mean_var = lastestuniquepoints[var].mean()
std_var = lastestuniquepoints[var].std()
ax.set_title(
    f"Shoreline point elevation (dune toe / veg edge)\n"
    f"mean={mean_var:.1f}\xb1{std_var:.1f} m",
    fontsize=10,
)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_aspect("equal")
plt.tight_layout()
plt.close()

fig.savefig(
    os.path.join(grandparent_folder, outputloc, outputfigname),
    dpi=300,
    bbox_inches="tight",
)
