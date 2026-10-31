"""The brain of the Sales Insights agent: question -> SQL -> guarded run on the GOLD layer -> short answer.

Why this works at all: the agent never touches raw data. It only sees the gold star schema, whose meaning
(grain, revenue definition, history rules) is written down in SCHEMA_DOC and RULES. Garbage in, garbage out -
so we made sure the garbage stays in bronze.
"""
import os
import re

import duckdb
from deltalake import DeltaTable

import llm
from common import LAKE

GOLD_TABLES = ["dim_product", "dim_date", "dim_customer", "fact_sales"]

SCHEMA_DOC = """
Star schema (gold layer):
fact_sales(source, order_id, date_key, customer_key, product_key, qty, unit_price, discount_pct, gross_amount, net_amount)
    grain: one row per order line. source is 'pos' (store) or 'web'. qty < 0 means a return.
dim_date(date_key, full_date, year, month, month_name, day_name)
dim_product(product_key, sku, product_name, category, list_price)
dim_customer(customer_key, email, full_name, city, tier, valid_from, valid_to, is_current)
    SCD Type 2: one row per customer VERSION. fact_sales.customer_key already points to the version valid on the sale date.
Joins: fact_sales.date_key = dim_date.date_key; fact_sales.product_key = dim_product.product_key;
       fact_sales.customer_key = dim_customer.customer_key
"""

RULES = """
Business rules agreed with Finance:
- "revenue" ALWAYS means SUM(net_amount). Use gross_amount only if the user says "gross".
- Cancelled orders are already excluded. Returns are already negative rows: do not subtract them again.
- Never filter sales by dim_customer.is_current.
- customer_key = -1 or product_key = -1 means unknown. Keep those rows unless the user asks to exclude them.
"""

DIALECTS = {
    "duckdb": "DuckDB SQL (use LIMIT n for top-n).",
    "fabric": "T-SQL for a Microsoft Fabric SQL analytics endpoint (use SELECT TOP n, never LIMIT; "
              "GROUP BY must list column names, never positions).",
}
BACKEND_NAME = os.getenv("BACKEND", "duckdb")

SQL_SYSTEM = f"""You are a careful analytics engineer. Write exactly ONE read-only SQL query that answers the question.
Dialect: {DIALECTS[BACKEND_NAME]}
{SCHEMA_DOC}
{RULES}
ROUND always takes two arguments, for example ROUND(x, 0).
Return ONLY the SQL. No explanation, no markdown.

Example question: What was revenue by category?
Example SQL: SELECT p.category, ROUND(SUM(f.net_amount), 0) AS revenue FROM fact_sales f JOIN dim_product p ON p.product_key = f.product_key GROUP BY p.category ORDER BY revenue DESC
"""

SUMMARY_SYSTEM = ("You explain query results to a business user in at most 3 short sentences. "
                  "Use only the numbers given. Mention that revenue means net revenue.")

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma|install|load|export|"
                       r"truncate|merge|exec|execute|call|set)\b", re.I)


def check_sql(sql: str) -> str:
    """The agent may only READ. Never trust model output - validate it like user input."""
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        raise ValueError("only one statement is allowed")
    if not re.match(r"(?is)^(select|with)\b", s):
        raise ValueError("only SELECT queries are allowed")
    if FORBIDDEN.search(s):
        raise ValueError("query contains a forbidden keyword")
    return s


def clean_sql(text: str) -> str:
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


class DuckBackend:
    """Reads the gold Delta tables into memory. Local, free, no cloud account."""

    def __init__(self):
        self.con = duckdb.connect()
        for t in GOLD_TABLES:
            self.con.register(t, DeltaTable(str(LAKE / "gold" / t)).to_pyarrow_table())
        self.con.execute("SET enable_external_access = false")   # the SQL cannot read files from disk

    def run(self, sql: str):
        rel = self.con.sql(sql)
        return rel.columns, rel.fetchall()


class FabricBackend:
    """Runs the same SQL on a Microsoft Fabric Lakehouse SQL analytics endpoint (needs pyodbc + ODBC Driver 18)."""

    def __init__(self):
        import pyodbc
        user = os.getenv("FABRIC_USER")                      # your Entra sign-in, e.g. you@company.com (optional)
        self.conn = pyodbc.connect(
            "Driver={ODBC Driver 18 for SQL Server};"
            f"Server={os.environ['FABRIC_SQL_ENDPOINT']};Database={os.environ['FABRIC_DATABASE']};"
            + (f"UID={user};" if user else "")
            + "Authentication=ActiveDirectoryInteractive;Encrypt=yes;"
        )

    def run(self, sql: str):
        cur = self.conn.cursor()
        cur.execute(sql)
        return [c[0] for c in cur.description], [tuple(r) for r in cur.fetchall()]


_backend = None


def backend():
    global _backend
    if _backend is None:
        _backend = FabricBackend() if BACKEND_NAME == "fabric" else DuckBackend()
    return _backend


def answer(question: str, chat=None) -> str:
    """chat(system, user, role) -> text. Defaults to llm.chat; langchain_agent.py passes its own."""
    chat = chat or llm.chat
    sql = clean_sql(chat(SQL_SYSTEM, question, role="sql"))
    last_error = None
    for attempt in (1, 2):
        try:
            sql = check_sql(sql)
            cols, rows = backend().run(sql)
            break
        except Exception as e:                      # let the model fix its own SQL once
            last_error = e
            if attempt == 2:
                return f"I could not answer that safely. Last error: {last_error}\nSQL tried:\n{sql}"
            sql = clean_sql(chat(SQL_SYSTEM, f"{question}\n\nYour previous SQL failed:\n{sql}\n"
                                             f"Error: {e}\nReturn the corrected SQL only.", role="sql"))
    shown = rows[:15]
    table = "\n".join(" | ".join(str(v) for v in r) for r in shown)
    if os.getenv("AGENT_SUMMARY", "on").lower() == "off":        # saves one model call (free tiers have tight limits)
        summary = "Net revenue figures from the gold layer:"
    else:
        summary = chat(SUMMARY_SYSTEM, f"Question: {question}\nColumns: {cols}\nRows: {shown}", role="summary")
    return f"{summary}\n\n{' | '.join(cols)}\n{table}\n\nSQL used:\n{sql}"


if __name__ == "__main__":       # quick test without A2A:  python agent_core.py "revenue by month"
    import sys
    print(answer(" ".join(sys.argv[1:]) or "What was total revenue?"))
