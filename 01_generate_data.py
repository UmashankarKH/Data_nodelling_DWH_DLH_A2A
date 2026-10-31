"""LAB 0 - Creates the messy raw data for FreshKart (a fictional grocery chain).

Run:  python 01_generate_data.py
Output: raw/pos_sales.csv, raw/web_orders.json, raw/products.csv, raw/crm_customers.csv

The mess is deliberate. Your job in Lab 1 is to find it.
"""
import csv
import json
import random
from datetime import date, timedelta

from faker import Faker

from common import RAW

random.seed(42)
Faker.seed(42)
fake = Faker("en_IN")
RAW.mkdir(exist_ok=True)

START, END = date(2026, 4, 1), date(2026, 9, 30)
DAYS = (END - START).days


def rand_day():
    return START + timedelta(days=random.randint(0, DAYS))


# ------------------------------------------------------------------ products
catalog = {
    "Dairy": ["Milk 1L", "Curd 500g", "Paneer 200g", "Butter 100g", "Ghee 500ml"],
    "Bakery": ["Bread", "Bun Pack", "Cake Slice", "Rusk"],
    "Snacks": ["Chips", "Namkeen", "Biscuits", "Chocolate"],
    "Beverages": ["Tea 250g", "Coffee 200g", "Juice 1L", "Cola 750ml"],
    "Staples": ["Rice 5kg", "Atta 5kg", "Dal 1kg", "Oil 1L", "Sugar 1kg"],
}
products = []
for category, names in catalog.items():
    for name in names:
        products.append({
            "sku": f"SKU{len(products) + 1:03d}",
            "product_name": name,
            "category": category,
            "list_price": random.choice([20, 35, 50, 80, 120, 250, 400, 550]),
        })
products[2]["category"] = "dairy"      # MESS: inconsistent casing
products[7]["category"] = "BAKERY"

with open(RAW / "products.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["sku", "product_name", "category", "list_price"])
    w.writeheader()
    w.writerows(products)

# ------------------------------------------------------------------ CRM customers (with history)
cities = ["Bengaluru", "Mumbai", "Chennai", "Hyderabad", "Pune"]
tiers = ["Silver", "Gold", "Platinum"]
customers = []
crm_rows = []
for i in range(300):
    email = f"user{i:03d}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com'])}"
    name = fake.name()
    city = random.choice(cities)
    tier = random.choice(tiers)
    customers.append(email)
    crm_rows.append({"crm_id": f"C{i:04d}", "email": email, "full_name": name,
                     "city": city, "tier": tier, "updated_on": "2026-01-01"})
    if random.random() < 0.25:  # this customer moved city mid-year -> a second row (history)
        new_city = random.choice([c for c in cities if c != city])
        moved_on = START + timedelta(days=random.randint(40, 140))
        crm_rows.append({"crm_id": f"C{i:04d}", "email": email, "full_name": name,
                         "city": new_city, "tier": random.choice(tiers),
                         "updated_on": moved_on.isoformat()})
# MESS: casing and spaces
for r in random.sample(crm_rows, 20):
    r["email"] = r["email"].upper()
for r in random.sample(crm_rows, 15):
    r["full_name"] = "  " + r["full_name"].lower() + " "

with open(RAW / "crm_customers.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(crm_rows[0].keys()))
    w.writeheader()
    w.writerows(crm_rows)

# ------------------------------------------------------------------ POS (store) sales
pos_rows = []


def pos_date(d):  # MESS: two date formats in one column
    return d.isoformat() if random.random() < 0.7 else d.strftime("%d/%m/%Y")


for n in range(1, 901):
    d = rand_day()
    email = random.choice(customers) if random.random() > 0.06 else ""   # MESS: walk-ins have no email
    if email and random.random() < 0.10:
        email = email.upper()                                            # MESS: casing
    store = random.choice(["BLR-01", "BLR-02", "MUM-01", "CHE-01", "HYD-01"])
    discount = random.choice([0, 0, 0, 5, 10])
    for p in random.sample(products, random.randint(1, 3)):              # 1 order has 1-3 lines
        pos_rows.append({
            "order_id": f"P-{n:05d}", "sold_on": pos_date(d), "store": store, "email": email,
            "sku": p["sku"], "qty": random.randint(1, 5), "unit_price": p["list_price"],
            "discount_pct": discount,
        })

# Returns: negative quantity on a new order id
for k, row in enumerate(random.sample(pos_rows, 60), start=1):
    d = min(END, START + timedelta(days=random.randint(0, DAYS)))
    pos_rows.append({**row, "order_id": f"R-{k:05d}", "sold_on": pos_date(d),
                     "qty": -random.randint(1, row["qty"]), "discount_pct": 0})

# MESS: a few lines for a product that does not exist in the catalog
for k in range(6):
    pos_rows.append({"order_id": f"P-9{k:04d}", "sold_on": pos_date(rand_day()), "store": "BLR-01",
                     "email": "", "sku": "SKU999", "qty": 1, "unit_price": 99, "discount_pct": 0})

# MESS: the nightly job ran twice -> exact duplicate rows
pos_rows += random.sample(pos_rows, 60)

with open(RAW / "pos_sales.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(pos_rows[0].keys()))
    w.writeheader()
    w.writerows(pos_rows)

# ------------------------------------------------------------------ Web orders (JSON, nested)
web_orders = []
for n in range(1, 701):
    d = rand_day()
    items = [{"sku": p["sku"], "qty": random.randint(1, 4), "price": p["list_price"]}
             for p in random.sample(products, random.randint(1, 3))]
    web_orders.append({
        "order_id": f"W-{n:05d}",
        "placed_at": f"{d.isoformat()}T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00",
        "email": random.choice(customers).lower(),
        "items": items,
        "coupon": "FRESH10" if random.random() < 0.2 else None,           # FRESH10 = 10% off
        "status": "cancelled" if random.random() < 0.08 else "delivered",  # cancelled must not count as revenue
    })

with open(RAW / "web_orders.json", "w", encoding="utf-8") as f:
    json.dump(web_orders, f, indent=1)

print("Created raw files in", RAW)
for p in sorted(RAW.iterdir()):
    print(f"  {p.name:20s} {p.stat().st_size / 1024:7.1f} KB")
