#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Estimate 1980-2000 SLR trends around NZ from PSMSL tide gauge records, and
assign the nearest gauge trend to each shoreline transect.

This fills the gap left by NZSeaRise_proj_novlm.csv, which only starts at 2000,
so it provides an independent pre-2000 SLR baseline for bruunvalidation.ipynb.

Output: output/validation/pre2000_slr_trends.csv
  - one row per PSMSL station: trend_1980_2000_mm_yr (relative, from tide gauge)
Output: output/validation/pre2000_slr_by_transect.csv
  - one row per Unique_ID: nearest_station, distance_km, slr_1980_2000_m
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_START = 1980
TRAIN_END = 2000
MIN_YEAR_COVERAGE = 8  # min valid monthly obs in a year to keep its annual mean
MIN_YEARS_FOR_TREND = 10  # min annual means required within window to fit a trend

# NZ RLR stations from the PSMSL station list (id, name, lat, lon).
# Coordinates are WGS84 (lat, lon) as published by PSMSL.
NZ_PSMSL_STATIONS = [
    (217, "AUCKLAND-WAITEMATA HARBOUR", -36.843, 174.769),
    (150, "AUCKLAND II", -36.843, 174.769),
    (978, "MOTURIKI ISLAND", -37.632, 176.185),
    (1590, "TAURANGA (SALISBURY WHARF)", -37.641, 176.181),
    (1613, "GISBORNE", -38.675, 178.022),
    (1750, "NAPIER", -39.476, 176.920),
    (221, "WELLINGTON HARBOUR", -41.284, 174.780),
    (500, "WELLINGTON II", -41.284, 174.780),
    (247, "PORT LYTTELTON", -43.606, 172.722),
    (259, "LYTTELTON II", -43.606, 172.722),
    (998, "TIMARU HARBOUR", -44.394, 171.256),
    (1643, "PORT CHALMERS", -45.815, 170.624),
    (252, "DUNEDIN", -45.879, 170.513),
    (213, "BLUFF (SOUTHLAND HARBOUR)", -46.598, 168.345),
    (993, "GREYMOUTH", -42.450, 171.200),
    (1004, "WESTPORT HARBOUR", -41.746, 171.595),
    (787, "NELSON", -41.261, 173.273),
    (1621, "WANGANUI", -39.945, 174.993),
    (996, "PORT TARANAKI", -39.056, 174.034),
    (1065, "WHANGAREI HARBOUR (MARSDEN POINT)", -35.757, 174.350),
    (1920, "CHATHAM ISLAND", -43.946, -176.561),
]

PSMSL_RLR_URL = "https://psmsl.org/data/obtaining/rlr.monthly.data/{id}.rlrdata"


RECORD_PATTERN = re.compile(r"(\d{4}\.\d{4})\s*;\s*(-?\d+)\s*;\s*\d+\s*;\s*\d+")


def fetch_station_monthly(station_id: int) -> pd.DataFrame:
    """Download and parse a PSMSL RLR monthly data file (whitespace/line-wrapping tolerant)."""
    url = PSMSL_RLR_URL.format(id=station_id)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    matches = RECORD_PATTERN.findall(resp.text)
    df = pd.DataFrame(matches, columns=["year_decimal", "height_mm"]).astype(float)
    df.loc[df["height_mm"] <= -99999, "height_mm"] = np.nan
    df["year"] = df["year_decimal"].astype(int)
    return df


def compute_trend_mm_per_yr(monthly: pd.DataFrame, start_year: int, end_year: int) -> tuple:
    """Fit a linear trend (mm/yr) to annual-mean sea level within [start_year, end_year]."""
    window = monthly[(monthly["year"] >= start_year) & (monthly["year"] <= end_year)]
    counts = window.groupby("year")["height_mm"].count()
    valid_years = counts[counts >= MIN_YEAR_COVERAGE].index
    annual = (
        window[window["year"].isin(valid_years)]
        .groupby("year")["height_mm"]
        .mean()
        .dropna()
    )
    if len(annual) < MIN_YEARS_FOR_TREND:
        return np.nan, len(annual)

    coeffs = np.polyfit(annual.index.values, annual.values, 1)
    return coeffs[0], len(annual)


def main():
    print(f"Fetching {len(NZ_PSMSL_STATIONS)} NZ PSMSL stations...")
    station_rows = []
    for station_id, name, lat, lon in NZ_PSMSL_STATIONS:
        try:
            monthly = fetch_station_monthly(station_id)
        except requests.RequestException as exc:
            print(f"  WARNING: failed to fetch station {station_id} ({name}): {exc}")
            continue

        trend, n_years = compute_trend_mm_per_yr(monthly, TRAIN_START, TRAIN_END)
        status = "ok" if not np.isnan(trend) else "insufficient_data"
        print(f"  {station_id:>5} {name:<35} trend={trend:.2f} mm/yr  n_years={n_years}  [{status}]"
              if not np.isnan(trend)
              else f"  {station_id:>5} {name:<35} trend=NaN  n_years={n_years}  [{status}]")

        station_rows.append(
            {
                "station_id": station_id,
                "station_name": name,
                "lat": lat,
                "lon": lon,
                "trend_1980_2000_mm_yr": trend,
                "n_years_used": n_years,
            }
        )

    stations = pd.DataFrame(station_rows)
    stations_path = OUTPUT_DIR / "pre2000_slr_trends.csv"
    stations.to_csv(stations_path, index=False)
    print(f"Saved station trends: {stations_path}")

    stations_valid = stations.dropna(subset=["trend_1980_2000_mm_yr"]).copy()
    if stations_valid.empty:
        raise RuntimeError("No PSMSL stations yielded a usable 1980-2000 trend.")

    # Assign nearest gauge to each shoreline transect (by NZTM distance).
    slpoints_path = PROJECT_ROOT / "slpoints_rates.csv.gz"
    if not slpoints_path.exists():
        raise FileNotFoundError(f"Missing required file: {slpoints_path}")

    sl = pd.read_csv(slpoints_path, low_memory=False, usecols=["Unique_ID", "IntersectX", "IntersectY", "Date"])
    sl["Unique_ID"] = pd.to_numeric(sl["Unique_ID"], errors="coerce").astype("Int64")
    sl["IntersectX"] = pd.to_numeric(sl["IntersectX"], errors="coerce")
    sl["IntersectY"] = pd.to_numeric(sl["IntersectY"], errors="coerce")
    sl["Date_dt"] = pd.to_datetime(sl["Date"], errors="coerce", dayfirst=True)
    sl = sl.dropna(subset=["Unique_ID", "IntersectX", "IntersectY"])

    # One representative point per transect (latest available position).
    latest_pts = (
        sl.sort_values("Date_dt")
        .groupby("Unique_ID", as_index=False)
        .last()[["Unique_ID", "IntersectX", "IntersectY"]]
    )

    # NZTM2000 (EPSG:2193) matches the shoreline point coordinates; convert
    # gauge lat/lon (WGS84) into the same CRS for distance calculations.
    to_nztm = Transformer.from_crs("EPSG:4326", "EPSG:2193", always_xy=True)
    gx, gy = to_nztm.transform(stations_valid["lon"].values, stations_valid["lat"].values)
    stations_valid["gauge_x"] = gx
    stations_valid["gauge_y"] = gy

    px = latest_pts["IntersectX"].to_numpy()[:, None]
    py = latest_pts["IntersectY"].to_numpy()[:, None]
    sx = stations_valid["gauge_x"].to_numpy()[None, :]
    sy = stations_valid["gauge_y"].to_numpy()[None, :]

    dist_m = np.hypot(px - sx, py - sy)
    nearest_idx = np.argmin(dist_m, axis=1)

    latest_pts["nearest_station_id"] = stations_valid["station_id"].values[nearest_idx]
    latest_pts["nearest_station_name"] = stations_valid["station_name"].values[nearest_idx]
    latest_pts["distance_km"] = dist_m[np.arange(len(latest_pts)), nearest_idx] / 1000.0
    latest_pts["trend_1980_2000_mm_yr"] = stations_valid["trend_1980_2000_mm_yr"].values[nearest_idx]
    latest_pts["slr_1980_2000_m"] = latest_pts["trend_1980_2000_mm_yr"] * (TRAIN_END - TRAIN_START) / 1000.0

    by_transect_path = OUTPUT_DIR / "pre2000_slr_by_transect.csv"
    latest_pts.to_csv(by_transect_path, index=False)
    print(f"Saved per-transect pre-2000 SLR: {by_transect_path}")
    print(latest_pts[["Unique_ID", "nearest_station_name", "distance_km", "slr_1980_2000_m"]].head())


if __name__ == "__main__":
    main()
