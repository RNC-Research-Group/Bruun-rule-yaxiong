#!/usr/bin/env python3
import os
import geopandas as gpd
from slr_settings import CONFIDENCE_LEVEL, YEARS, SCENARIOS, PERCENTILES_STR
from depthofclosure_settings import CD_METHOD, CD_METHOD_SUFFIX

# Iteration settings requested.
# Note: slr_settings.py defines WHICH confidence/year/scenario/percentile
# combinations are processed; it does not generate SLR values itself.
confidence_level = CONFIDENCE_LEVEL
years = YEARS
scenarios = SCENARIOS
percentiles = PERCENTILES_STR

currentyear = 2020  # used to convert recession distance to annual rate

current_script = os.path.abspath(__file__)
grandparent_folder = os.path.dirname(os.path.dirname(current_script))

inputfilename = os.path.join(grandparent_folder, f"output/bruunrule/bruunrule_{CD_METHOD_SUFFIX[CD_METHOD]}.gpkg")
slr_matchfile = os.path.join(grandparent_folder, "input/SLR/merged_SLR_match.gpkg")
if not os.path.exists(slr_matchfile):
    slr_matchfile = os.path.join(grandparent_folder, "input/SLR/SLR_match.gpkg")
confidence_level_filename = confidence_level.replace(" ", "_")

cd_suffix = CD_METHOD_SUFFIX[CD_METHOD]

# Base data
slr_match = gpd.read_file(slr_matchfile)
base_data = gpd.read_file(inputfilename)
print(slr_matchfile, slr_match.crs)
print(inputfilename, base_data.crs)

site_lookup = slr_match.drop_duplicates(subset="Unique_ID").set_index("Unique_ID")[
    "Site ID"
]

for year in years:
    for scenario in scenarios:
        slr_scenariofile = os.path.join(
            grandparent_folder,
            f"input/SLR/{confidence_level_filename}_y_{year}_s_{scenario}.gpkg",
        )

        if not os.path.exists(slr_scenariofile):
            print(f"Skip missing file: {slr_scenariofile}")
            continue

        slr_scenario = gpd.read_file(slr_scenariofile).to_crs(base_data.crs)
        years_delta = year - currentyear
        print(slr_scenariofile, slr_scenario.crs)
        print(f"Processing year={year}, scenario={scenario}, years_delta={years_delta}")

        for percentile in percentiles:
            percentile_col = (
                percentile
                if percentile in slr_scenario.columns
                else float(percentile)
            )
            if percentile_col not in slr_scenario.columns:
                print(
                    f"Skip percentile={percentile} for {slr_scenariofile}; column not found"
                )
                continue

            output_gpkg = os.path.join(
                grandparent_folder,
                f"output/bruunrule/bruunrule_{confidence_level_filename}_y_{year}_s_{scenario}_p_{percentile}.gpkg",
            )

            scenario_lookup = slr_scenario.drop_duplicates(subset="Site ID").set_index(
                "Site ID"
            )[percentile_col]

            out = base_data.copy()
            out["Site ID"] = out["Unique_ID"].map(site_lookup)
            out["S_SLR"] = out["Site ID"].map(scenario_lookup)
            out["R_SLR"] = out["S_SLR"] * out["R"]
            out["R_SLR_rate"] = out["R_SLR"] / years_delta

            # Project shoreline position along the same transect convention as step4
            # (x_new/y_new uses newx_profile = -R).
            out["proj_point_X"] = out["point_X"] + out["ux1"] * (-out["R_SLR"])
            out["proj_point_Y"] = out["point_Y"] + out["uy1"] * (-out["R_SLR"])

            out["lat"] = out.geometry.to_crs(4326).y
            out["lon"] = out.geometry.to_crs(4326).x

            projected_points = gpd.points_from_xy(
                out["proj_point_X"], out["proj_point_Y"], crs=out.crs
            ).to_crs(4326)
            out["proj_lat"] = projected_points.y
            out["proj_lon"] = projected_points.x

            wave_points = gpd.points_from_xy(
                out.wave_X, out.wave_Y, crs=out.crs
            ).to_crs(4326)
            out["wave_lat"] = wave_points.y
            out["wave_lon"] = wave_points.x

            cols_for_map = [
                "Unique_ID",
                "WLR",
                "Duration",
                "historic_retreat_obs_m",
                "dist_m",
                "mean_dist_to_coast",
                "CD",
                "B",
                "L",
                "R_bruun",
                "R",
                "tanbeta",
                "Site ID",
                "S_SLR",
                "R_SLR",
                "R_SLR_rate",
                "lat",
                "lon",
                "point_X",
                "point_Y",
                "ux1",
                "uy1",
                "proj_point_X",
                "proj_point_Y",
                "proj_lat",
                "proj_lon",
                "wave_lat",
                "wave_lon",
            ]

            output_csv = os.path.join(
                grandparent_folder,
                f"output/bruunrule/NZ_{confidence_level_filename}_y{year}_s{scenario}_p{percentile}_{cd_suffix}.csv",
            )
            out[cols_for_map].to_csv(output_csv, index=False, float_format="%.6f")
            out.to_file(output_gpkg, driver="GPKG")
            print(f"Saved SLR-enriched outputs: {output_gpkg}, {output_csv}")
