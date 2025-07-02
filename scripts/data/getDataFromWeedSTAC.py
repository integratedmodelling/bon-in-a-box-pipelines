
import requests
import json
from pathlib import Path
import sys
import tempfile
import rasterio
import numpy as np


data = biab_inputs()

parent_dir = Path(sys.argv[1])  # The base directory you want to use
#tmp_obj = Path(tempfile.mkdtemp(dir=parent_dir))
#tmp_dir = Path(tmp_obj.name)


error = []
collection = data['collection']
if collection == '' or collection is None or len(collection) == 0:
    error.append('Please specify a collection')

bbox = data['bbox']
if bbox=='' or bbox==None or len(bbox)==0:
	error.append('Please specify bounding box')

eo_band = data['eo_band']
if eo_band == '' or eo_band is None or len(eo_band) == 0:
    print ("Didn't specify an eo_band, will use the first one found in the assets")
      
search_endpoint = "https://catalogue.weed.apex.esa.int/search"

def get_http_url_from_s3_asset(asset_href: str) -> str:
    """
    Extracts the HTTP URL from the S3 Asset href for WEED Catalogue.
    """
    if asset_href.startswith("s3://"):
        if "waw3-1" in asset_href:
            return "https://s3.waw4-1.cloudferro.com/swift/v1/" + asset_href[5:]
        elif "waw4-1" in asset_href:
            return "https://s3.waw4-1.cloudferro.com/swift/v1/" + asset_href[5:]
        
        error.append(
            reason=f"Asset href '{asset_href}' does not contain a valid S3 bucket identifier."
        )
    
    return asset_href



# create the search string
search_payload = {
    "limit": 20,
    "collections": [collection],
    "filter-lang": "cql2-json",
    "bbox": bbox,
}

# execute the search
try:
    r = requests.post(search_endpoint, json=search_payload, timeout=(3, 5))
except requests.exceptions.Timeout:
    raise RuntimeError("Timeout while searching for feature items")
except requests.exceptions.RequestException as e:
    raise RuntimeError(f"Error while searching: {e}")

# handle response - here we have the rule that modelIDs have to be UNIQUE
features = None
if r.status_code == 200:
    search_results = r.json()
    if len(search_results["features"]) == 0:
        error.append("No features found for the specified collection and bounding box")
    
    print (f"Found {len(search_results['features'])} features in the collection '{collection}' within the specified bounding box.")
    features = search_results["features"][0]  #


    assets:dict = features.get("assets", {})
    assets_http_url:str = None

    if not assets:
        error.append("No assets found for the feature")
    else:
        print(f"Assets found: {list(assets.keys())}")

    for k, v in assets.items():
        if v.get("href", None) is None:
            error.append(f"Asset {k} has no href")
        else:
            print(f"Asset {k} href: {v['href']}")
            asset_http_url = get_http_url_from_s3_asset(v["href"])
            break


    band_data = None
    with rasterio.open(asset_http_url) as src:
        print(f"Opened COG File: {asset_http_url} Successfully")
        if eo_band in src.descriptions:
            band_index = src.descriptions.index(eo_band) + 1
            band_id = band_index
            band_data = src.read(band_id)
            profile = src.profile.copy()
            profile.update(count=1)  # Only one band
            band_data = np.expand_dims(band_data, axis=0)
        else:
            error.append(f"Band ID {eo_band} not found in COG file descriptions.")

    temp_tif = (Path(output_folder) / next(tempfile._get_candidate_names())).with_suffix(".tif")
    with rasterio.open(temp_tif, 'w', **profile) as dst:
        dst.write(band_data)

    out = {}
    out['data'] = str(temp_tif)
   # json_string = json.dumps(out)
    biab_output("data", str(temp_tif))
   # output_path = output_folder  + "/" + "output.json"

    #with open(output_path, "w") as f:
    #    json.dump(json_string, f, indent=2)

    if len(error) > 0:
        biab_output("error", "; ".join(error))

elif r.status_code == 400:
    error.append("Bad Request – validation errors:")
else:
    error.append(f"Unexpected status {r.status_code}:")

