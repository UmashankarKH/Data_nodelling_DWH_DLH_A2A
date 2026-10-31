"""LAB 4 - Medallion lakehouse: bronze -> silver -> gold as Delta tables, plus time travel.

Run:  python 04_medallion_delta.py

bronze = raw, exactly as received (+ audit columns). Never edited.
silver = cleaned, typed, de-duplicated. One trusted copy of each business entity.
gold   = modelled for questions: the star schema from Lab 2/3, now stored as Delta tables.
"""
import json
import shutil
from datetime import datetime, timezone

import duckdb
import pandas as pd
from deltalake import DeltaTable, write_deltalake

from common import LAKE, RAW

if LAKE.exists():
    shutil.rmtree(LAKE)
now = datetime.now(timezone.utc).isoformat(timespec="seconds")
con = duckdb.connect()  # in-memory engine; the Delta folders are the storage


def write(df, layer, name):
    write_deltalake(str(LAKE / layer / name), df, mode="overwrite")
    print(f"  wrote {layer}/{name:18s} {df.shape[0]:6d} rows")


def read(layer, name):
    return DeltaTable(str(LAKE / layer / name)).to_pyarrow_table()


# ================================================================ BRONZE: land the data as-is
print("BRONZE")
for name, fname in [("pos_sales", "pos_sales.csv"), ("products", "products.csv"), ("crm_customers", "crm_customers.csv")]:
    df = pd.read_csv(RAW / fname, dtype=str, keep_default_na=False)      # everything as text: no decisions yet
    df["_source_file"], df["_ingested_at"] = fname, now
    write(df, "bronze", name)

web = pd.DataFrame(json.loads((RAW / "web_orders.json").read_text(encoding="utf-8")))
web["items"] = web["items"].map(json.dumps)                               # keep the nested part as raw JSON text
web["_source_file"], web["_ingested_at"] = "web_orders.json", now
write(web, "bronze", "web_orders")

for n in ["pos_sales", "web_orders", "products", "crm_customers"]:
    con.register(f"bronze_{n}", read("bronze", n))

# ================================================================ SILVER: clean, type, de-duplicate
print("SILVER")
silver_sales = con.sql("""
    WITH pos AS (
        SELECT order_id,
               COALESCE(TRY_STRPTIME(sold_on, '%Y-%m-%d'), TRY_STRPTIME(sold_on, '%d/%m/%Y'))::DATE AS sold_on,
               NULLIF(LOWER(TRIM(email)), '') AS email, sku,
               CAST(qty AS INTEGER) AS qty, CAST(unit_price AS DOUBLE) AS unit_price,
               CAST(discount_pct AS DOUBLE) AS discount_pct, 'pos' AS source, 'completed' AS status
        FROM bronze_pos_sales
    ),
    web AS (
        SELECT order_id, CAST(placed_at AS TIMESTAMP)::DATE AS sold_on,
               NULLIF(LOWER(TRIM(email)), '') AS email,
               i.sku AS sku, CAST(i.qty AS INTEGER) AS qty, CAST(i.price AS DOUBLE) AS unit_price,
               CASE WHEN coupon = 'FRESH10' THEN 10.0 ELSE 0.0 END AS discount_pct, 'web' AS source, status
        FROM (SELECT *, UNNEST(json_transform(items, '[{"sku":"VARCHAR","qty":"INTEGER","price":"DOUBLE"}]')) AS i
              FROM bronze_web_orders)
    )
    SELECT * FROM (SELECT * FROM pos UNION ALL SELECT * FROM web)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id, sku ORDER BY sold_on) = 1
""").to_arrow_table()
write(silver_sales, "silver", "sales")

write(con.sql("""
    SELECT sku, product_name, UPPER(LEFT(category, 1)) || LOWER(SUBSTR(category, 2)) AS category,
           CAST(list_price AS DOUBLE) AS list_price
    FROM bronze_products""").to_arrow_table(), "silver", "products")

write(con.sql("""
    SELECT LOWER(TRIM(email)) AS email, TRIM(full_name) AS full_name, city, tier, CAST(updated_on AS DATE) AS valid_from
    FROM bronze_crm_customers""").to_arrow_table(), "silver", "customers_history")

for n in ["sales", "products", "customers_history"]:
    con.register(f"silver_{n}", read("silver", n))

# ================================================================ GOLD: the star schema, as Delta tables
print("GOLD")
write(con.sql("""
    SELECT ROW_NUMBER() OVER (ORDER BY sku) AS product_key, sku, product_name, category, list_price FROM silver_products
    UNION ALL SELECT -1, 'UNKNOWN', 'Unknown product', 'Unknown', 0
""").to_arrow_table(), "gold", "dim_product")

write(con.sql("""
    SELECT CAST(STRFTIME(d, '%Y%m%d') AS INTEGER) AS date_key, d::DATE AS full_date, YEAR(d) AS year,
           MONTH(d) AS month, MONTHNAME(d) AS month_name, DAYNAME(d) AS day_name
    FROM generate_series(DATE '2026-04-01', DATE '2026-09-30', INTERVAL 1 DAY) AS t(d)
""").to_arrow_table(), "gold", "dim_date")

write(con.sql("""
    WITH v AS (SELECT *, LEAD(valid_from) OVER (PARTITION BY email ORDER BY valid_from) AS next_from FROM silver_customers_history)
    SELECT ROW_NUMBER() OVER (ORDER BY email, valid_from) AS customer_key, email, full_name, city, tier, valid_from,
           COALESCE(next_from - 1, DATE '9999-12-31') AS valid_to, next_from IS NULL AS is_current
    FROM v
    UNION ALL SELECT -1, 'unknown', 'Walk-in / unknown', 'Unknown', 'None', DATE '1900-01-01', DATE '9999-12-31', true
""").to_arrow_table(), "gold", "dim_customer")
for n in ["dim_product", "dim_date", "dim_customer"]:
    con.register(f"gold_{n}", read("gold", n))

write(con.sql("""
    SELECT s.source, s.order_id, CAST(STRFTIME(s.sold_on, '%Y%m%d') AS INTEGER) AS date_key,
           COALESCE(c.customer_key, -1) AS customer_key, COALESCE(p.product_key, -1) AS product_key,
           s.qty, s.unit_price, s.discount_pct,
           s.qty * s.unit_price AS gross_amount,
           s.qty * s.unit_price * (1 - s.discount_pct / 100.0) AS net_amount
    FROM silver_sales s
    LEFT JOIN gold_dim_product  p ON p.sku = s.sku
    LEFT JOIN gold_dim_customer c ON c.email = s.email AND s.sold_on BETWEEN c.valid_from AND c.valid_to
    WHERE s.status <> 'cancelled'
""").to_arrow_table(), "gold", "fact_sales")
con.register("gold_fact_sales", read("gold", "fact_sales"))

# ================================================================ THE AHA: "what was revenue?"
print("\n=== Same question, three answers: 'What was total revenue Apr-Sep 2026?'")
print(con.sql("""
    WITH raw_pos AS (SELECT SUM(CAST(qty AS INTEGER) * CAST(unit_price AS DOUBLE)) AS v FROM bronze_pos_sales),
         raw_web AS (SELECT SUM(i.qty * i.price) AS v
                     FROM (SELECT UNNEST(json_transform(items, '[{"sku":"VARCHAR","qty":"INTEGER","price":"DOUBLE"}]')) AS i
                           FROM bronze_web_orders))
    SELECT 'Sales agent (raw files: duplicates, cancelled, no discounts)' AS who, ROUND((SELECT v FROM raw_pos) + (SELECT v FROM raw_web)) AS revenue
    UNION ALL SELECT 'Clean but gross (no discounts applied)', ROUND(SUM(gross_amount)) FROM gold_fact_sales
    UNION ALL SELECT 'Finance agent (gold: net of discounts, returns, cancelled)', ROUND(SUM(net_amount)) FROM gold_fact_sales
""").df().to_string(index=False))

# ================================================================ TIME TRAVEL: a bad day, and the undo button
print("\n=== Time travel: somebody deletes all web orders from silver.sales by mistake")
path = str(LAKE / "silver" / "sales")
dt = DeltaTable(path)
rows = lambda d: d.to_pyarrow_table().num_rows
print(f"  version {dt.version()}: {rows(dt)} rows")

dt.delete("source = 'web'")
dt = DeltaTable(path)
print(f"  after the bad DELETE, version {dt.version()}: {rows(dt)} rows   <- the agent would now report wrong revenue")

print("  history:", [h.get("operation") for h in dt.history()])
old = DeltaTable(path, version=0)
print(f"  reading version 0 still works: {rows(old)} rows")

dt.restore(0)
dt = DeltaTable(path)
print(f"  after RESTORE, version {dt.version()}: {rows(dt)} rows   <- fixed, and the mistake is in the audit trail")
con.close()
