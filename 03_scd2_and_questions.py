"""LAB 3 - Customer history with SCD Type 2, then answer business questions.

Run:  python 03_scd2_and_questions.py      (run 02_star_schema.py first)

Story: Priya lived in Mumbai in May and moved to Pune in July. Which city should her May purchases count for?
  Type 1 (overwrite)  -> Pune. History is lost; May revenue silently moves to Pune.
  Type 2 (new row)    -> Mumbai for May, Pune for July. History is kept.
"""
import duckdb

from common import RAW, WAREHOUSE_DB

con = duckdb.connect(str(WAREHOUSE_DB))
crm = (RAW / "crm_customers.csv").as_posix()


def show(title, sql):
    print(f"\n=== {title}")
    print(con.sql(sql).df().to_string(index=False))


# ---------------------------------------------------------------- 1. SCD Type 2 customer dimension
con.execute(f"""
CREATE OR REPLACE TABLE dim_customer_scd2 AS
WITH h AS (
    SELECT LOWER(TRIM(email)) AS email, TRIM(full_name) AS full_name, city, tier,
           CAST(updated_on AS DATE) AS valid_from
    FROM read_csv('{crm}', header = true, all_varchar = true)
),
v AS (
    SELECT *, LEAD(valid_from) OVER (PARTITION BY email ORDER BY valid_from) AS next_from FROM h
)
SELECT ROW_NUMBER() OVER (ORDER BY email, valid_from)    AS customer_key,   -- surrogate key: one per VERSION
       email, full_name, city, tier,
       valid_from,
       COALESCE(next_from - 1, DATE '9999-12-31')        AS valid_to,
       next_from IS NULL                                 AS is_current
FROM v
""")
con.execute("INSERT INTO dim_customer_scd2 VALUES (-1, 'unknown', 'Walk-in / unknown', 'Unknown', 'None', "
            "DATE '1900-01-01', DATE '9999-12-31', true)")

show("A customer who moved: two rows, two surrogate keys", """
    SELECT customer_key, email, city, valid_from, valid_to, is_current
    FROM dim_customer_scd2
    WHERE email IN (SELECT email FROM dim_customer_scd2 GROUP BY email HAVING COUNT(*) > 1 LIMIT 1)
    ORDER BY valid_from
""")

# ---------------------------------------------------------------- 2. fact table that picks the version valid on the sale date
con.execute("""
CREATE OR REPLACE TABLE fact_sales_v2 AS
SELECT s.source, s.order_id,
       CAST(STRFTIME(s.sold_on, '%Y%m%d') AS INTEGER)      AS date_key,
       COALESCE(c.customer_key, -1)                        AS customer_key,
       COALESCE(p.product_key, -1)                         AS product_key,
       s.qty, s.unit_price, s.discount_pct,
       s.qty * s.unit_price                                AS gross_amount,
       s.qty * s.unit_price * (1 - s.discount_pct / 100.0) AS net_amount
FROM stg_sales s
LEFT JOIN dim_product p       ON p.sku = s.sku
LEFT JOIN dim_customer_scd2 c ON c.email = s.email AND s.sold_on BETWEEN c.valid_from AND c.valid_to
WHERE s.status <> 'cancelled'
""")

show("Type 1 vs Type 2: same sales, different story by city", """
    WITH t1 AS (SELECT c.city, SUM(f.net_amount) AS rev FROM fact_sales f JOIN dim_customer c USING (customer_key) GROUP BY 1),
         t2 AS (SELECT c.city, SUM(f.net_amount) AS rev FROM fact_sales_v2 f JOIN dim_customer_scd2 c USING (customer_key) GROUP BY 1)
    SELECT COALESCE(t1.city, t2.city) AS city,
           ROUND(t1.rev) AS type1_current_city,
           ROUND(t2.rev) AS type2_city_at_time_of_sale,
           ROUND(t2.rev - t1.rev) AS difference
    FROM t1 FULL JOIN t2 ON t1.city = t2.city
    ORDER BY city
""")

# ---------------------------------------------------------------- 3. five business questions (your turn: write Q4 and Q5 yourself first)
show("Q1  Net revenue by month", """
    SELECT d.month_name, ROUND(SUM(f.net_amount)) AS net_revenue
    FROM fact_sales_v2 f JOIN dim_date d USING (date_key)
    GROUP BY d.month, d.month_name ORDER BY d.month
""")

show("Q2  Top 5 products by net revenue", """
    SELECT p.product_name, p.category, ROUND(SUM(f.net_amount)) AS net_revenue
    FROM fact_sales_v2 f JOIN dim_product p USING (product_key)
    GROUP BY 1, 2 ORDER BY net_revenue DESC LIMIT 5
""")

show("Q3  Net revenue by customer tier (tier at time of sale)", """
    SELECT c.tier, ROUND(SUM(f.net_amount)) AS net_revenue, COUNT(DISTINCT f.order_id) AS orders
    FROM fact_sales_v2 f JOIN dim_customer_scd2 c USING (customer_key)
    GROUP BY 1 ORDER BY net_revenue DESC
""")

show("Q4  Return rate by category (value of returns / value of sales)", """
    SELECT p.category,
           ROUND(COALESCE(-SUM(CASE WHEN f.qty < 0 THEN f.net_amount END), 0)) AS returned_value,
           ROUND(SUM(CASE WHEN f.qty > 0 THEN f.net_amount END))  AS sold_value,
           ROUND(100 * COALESCE(-SUM(CASE WHEN f.qty < 0 THEN f.net_amount END), 0)
                       / SUM(CASE WHEN f.qty > 0 THEN f.net_amount END), 1) AS return_rate_pct
    FROM fact_sales_v2 f JOIN dim_product p USING (product_key)
    GROUP BY 1 ORDER BY return_rate_pct DESC
""")

show("Q5  Web vs store share of net revenue", """
    SELECT source, ROUND(SUM(net_amount)) AS net_revenue,
           ROUND(100 * SUM(net_amount) / SUM(SUM(net_amount)) OVER (), 1) AS share_pct
    FROM fact_sales_v2 GROUP BY source ORDER BY net_revenue DESC
""")
con.close()
