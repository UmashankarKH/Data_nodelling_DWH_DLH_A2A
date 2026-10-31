"""LAB 2 - Build a star schema in DuckDB (a tiny data warehouse in one file).

Run:  python 02_star_schema.py
Output: warehouse.duckdb with dim_date, dim_product, dim_customer, fact_sales

GRAIN of fact_sales = one row per order line (one product on one order).
Say the grain out loud before you write any SQL. Everything else follows from it.
"""
import duckdb

from common import RAW, WAREHOUSE_DB

con = duckdb.connect(str(WAREHOUSE_DB))
pos, web = (RAW / "pos_sales.csv").as_posix(), (RAW / "web_orders.json").as_posix()
products, crm = (RAW / "products.csv").as_posix(), (RAW / "crm_customers.csv").as_posix()

# ---------------------------------------------------------------- 1. staging: one clean, unified sales table
con.execute(f"""
CREATE OR REPLACE TABLE stg_sales AS
WITH pos AS (
    SELECT order_id,
           COALESCE(TRY_STRPTIME(sold_on, '%Y-%m-%d'), TRY_STRPTIME(sold_on, '%d/%m/%Y'))::DATE AS sold_on,
           NULLIF(LOWER(TRIM(email)), '')            AS email,
           sku,
           CAST(qty AS INTEGER)                      AS qty,
           CAST(unit_price AS DOUBLE)                AS unit_price,
           CAST(discount_pct AS DOUBLE)              AS discount_pct,
           'pos'                                     AS source,
           'completed'                               AS status
    FROM read_csv('{pos}', header = true, all_varchar = true)
),
web AS (
    SELECT order_id,
           CAST(placed_at AS TIMESTAMP)::DATE        AS sold_on,
           NULLIF(LOWER(TRIM(email)), '')            AS email,
           i.sku                                     AS sku,
           CAST(i.qty AS INTEGER)                    AS qty,
           CAST(i.price AS DOUBLE)                   AS unit_price,
           CASE WHEN coupon = 'FRESH10' THEN 10.0 ELSE 0.0 END AS discount_pct,
           'web'                                     AS source,
           status
    FROM (SELECT *, UNNEST(items) AS i FROM read_json('{web}', format = 'array'))
)
SELECT * FROM (SELECT * FROM pos UNION ALL SELECT * FROM web)
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id, sku ORDER BY sold_on) = 1   -- removes the double-loaded rows
""")

# ---------------------------------------------------------------- 2. dimensions
con.execute(f"""
CREATE OR REPLACE TABLE dim_product AS
SELECT ROW_NUMBER() OVER (ORDER BY sku) AS product_key,
       sku, product_name,
       UPPER(LEFT(category, 1)) || LOWER(SUBSTR(category, 2)) AS category,   -- fixes dairy / BAKERY
       CAST(list_price AS DOUBLE) AS list_price
FROM read_csv('{products}', header = true, all_varchar = true)
""")
con.execute("INSERT INTO dim_product VALUES (-1, 'UNKNOWN', 'Unknown product', 'Unknown', 0)")  # never drop a fact row

con.execute("""
CREATE OR REPLACE TABLE dim_date AS
SELECT CAST(STRFTIME(d, '%Y%m%d') AS INTEGER) AS date_key,
       d::DATE                  AS full_date,
       YEAR(d)                  AS year,
       QUARTER(d)               AS quarter,
       MONTH(d)                 AS month,
       MONTHNAME(d)             AS month_name,
       DAYNAME(d)               AS day_name,
       DAYOFWEEK(d) IN (0, 6)   AS is_weekend
FROM generate_series(DATE '2026-04-01', DATE '2026-09-30', INTERVAL 1 DAY) AS t(d)
""")

# Type 1 customer dimension: keep only the LATEST row per customer (history is lost - see Lab 3)
con.execute(f"""
CREATE OR REPLACE TABLE dim_customer AS
SELECT ROW_NUMBER() OVER (ORDER BY email) AS customer_key, email, full_name, city, tier
FROM (
    SELECT LOWER(TRIM(email)) AS email, TRIM(full_name) AS full_name, city, tier
    FROM read_csv('{crm}', header = true, all_varchar = true)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY LOWER(TRIM(email)) ORDER BY updated_on DESC) = 1
)
""")
con.execute("INSERT INTO dim_customer VALUES (-1, 'unknown', 'Walk-in / unknown', 'Unknown', 'None')")

# ---------------------------------------------------------------- 3. the fact table
con.execute("""
CREATE OR REPLACE TABLE fact_sales AS
SELECT s.source,
       s.order_id,
       CAST(STRFTIME(s.sold_on, '%Y%m%d') AS INTEGER)      AS date_key,
       COALESCE(c.customer_key, -1)                        AS customer_key,
       COALESCE(p.product_key, -1)                         AS product_key,
       s.qty,
       s.unit_price,
       s.discount_pct,
       s.qty * s.unit_price                                AS gross_amount,
       s.qty * s.unit_price * (1 - s.discount_pct / 100.0) AS net_amount
FROM stg_sales s
LEFT JOIN dim_product  p ON p.sku   = s.sku
LEFT JOIN dim_customer c ON c.email = s.email
WHERE s.status <> 'cancelled'                              -- business rule: cancelled orders are not revenue
""")

# ---------------------------------------------------------------- 4. sanity checks (an FDE always reconciles)
print("\nRow counts")
print(con.sql("""
    SELECT 'stg_sales (all lines)' AS what, COUNT(*) AS n FROM stg_sales
    UNION ALL SELECT 'stg_sales cancelled', COUNT(*) FROM stg_sales WHERE status = 'cancelled'
    UNION ALL SELECT 'fact_sales', COUNT(*) FROM fact_sales
    UNION ALL SELECT 'fact rows with unknown product', COUNT(*) FROM fact_sales WHERE product_key = -1
    UNION ALL SELECT 'fact rows with unknown customer', COUNT(*) FROM fact_sales WHERE customer_key = -1
""").df().to_string(index=False))

print("\nNet revenue by month")
print(con.sql("""
    SELECT d.month_name, ROUND(SUM(f.net_amount)) AS net_revenue
    FROM fact_sales f JOIN dim_date d USING (date_key)
    GROUP BY d.month, d.month_name ORDER BY d.month
""").df().to_string(index=False))
con.close()
print("\nDone -> warehouse.duckdb")
