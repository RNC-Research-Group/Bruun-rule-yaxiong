# Bruun-rule-yaxiong

preprocess:
1. preprocess1_getlatestshorelinepoints.py
get the latest shoreline points in NZCCD dataset from .shp file
Merged Intersects_UniqueID folder is for all data; output shoreline point filename will be JaMoNoRaSoWa. 
Merged Intersects_UniqueID_test folder is for shoreline points from Waiheke island as an example to test; output shoreline point filename will be Wa

2. preprocess1_wavedatadownloadfromwebserver.py
download WHACS .nc files from https://wave.storm-surge.cloud.edu.au/WHACS/hs_NZ/

3. preprocess2_dunepeak.py
extract dune peak from CoastDEM. buffer_dist is used for changing the size of the buffer

4. preprocess2_matchSLRandshorelinepoints.py
match shoreline points from NZCCD  to sea level rise points from OCC

5. preprocess2_SLRscenario.py
choose one SLR scenario
user can custom year, scenario, and confidence level here

data processing
1. step1_expandpolygonandfilterwavegauge.py
note buffer distance here is for searching the wavegauge; different from preprocess2_dunepeak.py

2. step2_H12handT12h.py
get Hs12hr/year and T12hr/year; user can change the min and maxdate for calculation.
in current code, T12hr/year is the mean of T01_12h_y, T02_12h_y, T0m1_12h_y, and Tp_12h_y.

3. step3_matchwgandshorelinepoints.py
match shoreline points from NZCCD to wave points from WHACS.
for all NZCCD points, it takes 24 hrs to run.

4. step4_bruunrule.py
apply Bruun's rule to calculate the R for unit sea level rise (S=1).
buffer_dist here should be the same as preprocess2_dunepeak.py
isexportplot=0 or 1 # 0 = do not export transect plots; 1 = export every transect plot (time-consuming)

5. step5_addSLR.py
add SLE scenario to the R calculated in step4_bruunrule.py
buffer_dist here should be the same as preprocess2_dunepeak.py
confidence_level, year, percentile and scenario should be same as preprocess2_SLRscenario.py
The current year is used to calculate the erosion rate. Ideally, it should correspond to the mean date of the most recent shoreline points.


post data processing
1. postprocess_plotdunepeak.py
plot dunepeak elevation. 
buffer_dist here should be the same as preprocess2_dunepeak.py

2. postprocess_plotslope.py
plot slope of active coast profile
buffer_dist here should be the same as preprocess2_dunepeak.py

3. postprocess_plotRandER.py
plot Recession value and erosion rate
buffer_dist here should be the same as preprocess2_dunepeak.py
confidence_level, year, percentile and scenario should be same as preprocess2_SLRscenario.py

