"""Shared paths for all labs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"                      # messy source files (Lab 1)
LAKE = ROOT / "lakehouse"               # bronze / silver / gold Delta tables (Lab 4)
WAREHOUSE_DB = ROOT / "warehouse.duckdb"  # star schema (Lab 2 and 3)
