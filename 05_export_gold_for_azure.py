"""AZURE SHOWCASE helper - export the gold tables as Parquet so you can upload them to a Fabric Lakehouse.

Run:  python 05_export_gold_for_azure.py      (run 04_medallion_delta.py first)
Output: export/dim_product.parquet, dim_date.parquet, dim_customer.parquet, fact_sales.parquet
"""
import pyarrow.parquet as pq
from deltalake import DeltaTable

from common import LAKE, ROOT

out = ROOT / "export"
out.mkdir(exist_ok=True)
for t in ["dim_product", "dim_date", "dim_customer", "fact_sales"]:
    table = DeltaTable(str(LAKE / "gold" / t)).to_pyarrow_table()
    pq.write_table(table, out / f"{t}.parquet")
    print(f"  {t}.parquet  {table.num_rows} rows")
print("Upload these four files to the Lakehouse 'Files' area, then right-click each file -> Load to Tables.")
