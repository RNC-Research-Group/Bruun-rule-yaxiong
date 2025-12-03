#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 18 13:44:03 2025

@author: yshe948
"""

# -*- coding: utf-8 -*-
"""
Download WHACS .nc files from https://wave.storm-surge.cloud.edu.au/WHACS/hs_NZ/
"""

import requests
from bs4 import BeautifulSoup
import os

# --- Settings ---
#input
variable='t0m1'

base_url = f"https://wave.storm-surge.cloud.edu.au/WHACS/{variable}_NZ/"
current_script = os.path.abspath(__file__)
grandparent_folder =  os.path.dirname(os.path.dirname(current_script))

#output
output_folder = os.path.join(grandparent_folder,f"input\wavedata\whacs_{variable}")#f"data/whacs_{variable}"
os.makedirs(output_folder, exist_ok=True)

print("Accessing WHACS site ...")
response = requests.get(base_url)
if response.status_code != 200:
    raise ConnectionError(f"Failed to access {base_url} (status {response.status_code})")

# --- Parse HTML to find all .nc files ---
soup = BeautifulSoup(response.text, "html.parser")
file_links = [a["href"] for a in soup.find_all("a") if a["href"].endswith(".nc")]

print(f"Found {len(file_links)} NetCDF files on the server.")
for f in file_links[:5]:
    print("Example file:", f)  # show a few examples

# --- Optional: Download all files (or a subset) ---
for filename in file_links:
    file_url = base_url + filename
    local_path = os.path.join(output_folder, filename)

    # Skip if already downloaded
    if os.path.exists(local_path):
        print(f"File already exists: {filename}")
        continue

    print(f"Downloading {filename} ...")
    with requests.get(file_url, stream=True) as r:
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

print("✅ All available files downloaded successfully!")
