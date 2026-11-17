"""Download the public Online Retail transactions into data/.  python src/get_data.py"""
import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "https://raw.githubusercontent.com/aakashsyadav1999/online-retail-dataset/main/online%2Bretail.zip"
D = Path(__file__).resolve().parents[1] / "data"
D.mkdir(exist_ok=True)
out = D / "online_retail.csv"
if out.exists():
    print("data already present")
else:
    print("downloading (~23 MB)")
    with urllib.request.urlopen(URL) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    df = pd.read_excel(io.BytesIO(z.read(z.namelist()[0])))
    for c in ["InvoiceNo", "StockCode", "Description", "Country"]:
        df[c] = df[c].astype(str)
    df.to_csv(out, index=False)
    print("saved", out, len(df), "rows")
