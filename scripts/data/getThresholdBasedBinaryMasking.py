import sys
import tempfile
import numpy as np
from pathlib import Path
import rasterio


inputs = biab_inputs()
error = []

data_path = inputs['data']
if data_path == '' or data_path is None or len(data_path) == 0:
    error.append('Please specify a data path')

print ("Found data path: ", data_path)


threshold = inputs['threshold']
if threshold is None:
    error.append('Please specify a threshold value')


temp_tif = (Path(output_folder) / next(tempfile._get_candidate_names())).with_suffix(".tif")
with rasterio.open(data_path) as src:
    profile = src.profile
    data = src.read(1)  # Read the first band
    nodata = src.nodata

    if nodata is not None:
        data[data == nodata] = 255
    # Generate binary mask: 1 where data >= threshold, else 0
    binary_mask = np.where(data >= threshold, 1, 0).astype(np.uint8)

    # Update profile for single-band uint8 mask
    profile.update(
        dtype=rasterio.uint8,
        count=1,
        nodata=255
    )

    # Write the binary mask to a new raster file
    with rasterio.open(temp_tif, "w", **profile) as dst:
        dst.write(binary_mask, 1)

biab_output("binary_mask", str(temp_tif))

if len(error) > 0:
    biab_output("error", "; ".join(error))
