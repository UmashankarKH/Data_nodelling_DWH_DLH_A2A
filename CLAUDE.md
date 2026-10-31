# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A teaching lab ("FreshKart"): messy raw sales data -> star schema -> SCD Type 2 -> medallion Delta lakehouse -> a read-only text-to-SQL "Sales Insights" agent exposed over the A2A protocol. Everything runs locally. Learner-facing docs are `README.md` and `SETUP.md`; `FOUNDRY_DEMO.md`, `Dockerfile`, `foundry_*.py` and `requirements-extras.txt` are a trainer-only Azure/Foundry demo (not run against Azure).

There is no test suite, linter, or build step. Scripts are verified by running them.

## Commands

Use the `.venv` in the repo root (activate with `.venv\Scripts\Activate.ps1` on Windows). One-time setup: `python setup.py` (`--provider mock|ollama` for non-interactive).

Labs must run in order, since each consumes the previous one's output:

```
python 01_generate_data.py                  # writes raw/ (messy CSV/JSON)
python 02_star_schema.py                    # builds warehouse.duckdb
python 03_scd2_and_questions.py             # SCD2 + business questions
python 04_medallion_delta.py                # rebuilds lakehouse/{bronze,silver,gold} (deletes lakehouse/ first)
python a2a_server.py                        # agent on http://127.0.0.1:9999 (card at /.well-known/agent-card.json)
python a2a_client.py "revenue by month"     # second terminal
python agent_core.py "Top 5 products by revenue?"   # agent brain without A2A
python check_llm.py [--list [filter]]       # test/list models
```

For offline work with no API key, set `LLM_PROVIDER=mock` (canned SQL keyed on words like "month", "product", "city", "web"/"store" in `llm._mock`).

## Architecture

- **`common.py`** defines the shared paths (`RAW`, `LAKE`, `WAREHOUSE_DB`); all labs import from it.
- **Lab 4 (`04_medallion_delta.py`)** is the core data pipeline: bronze (everything as text + `_source_file`/`_ingested_at`), silver (typed, deduped on `order_id, sku`; POS and web unified), gold (star schema: `dim_product`, `dim_date`, `dim_customer` SCD2, `fact_sales`). Unknown dimension members use key `-1`. It also demonstrates Delta time travel (delete, then restore to version 0).
- **`agent_core.py`** answers a question: LLM writes SQL -> `check_sql` (single SELECT/WITH only, forbidden-keyword regex) -> run on backend -> optional LLM summary. It retries once, feeding the error back to the model. The agent reads **only the gold layer**. `SCHEMA_DOC` and `RULES` are the agent's contract with Finance (e.g. revenue = `SUM(net_amount)`, never filter by `is_current`). If you change gold table schemas or business rules, update those strings and the `_mock` SQL in `llm.py`.
- **Backends** (env `BACKEND`): `duckdb` (default; registers gold Delta tables in memory, external access disabled) or `fabric` (pyodbc to a Microsoft Fabric SQL endpoint; needs `FABRIC_SQL_ENDPOINT`, `FABRIC_DATABASE`, and uses T-SQL dialect instructions).
- **`llm.py`** is a single wrapper over any OpenAI-compatible endpoint. Provider is chosen by `LLM_PROVIDER` (`openrouter`, `nvidia`, `ollama`, `azure`, `mock`); `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_API` override presets. `azure` uses the Responses API; others use chat completions. `<think>` blocks are stripped from output.
- **`a2a_server.py`** wraps `agent_core.answer` in an A2A `AgentExecutor` (a2a-sdk 1.x, pinned `>=1.2,<2`) served by Starlette/uvicorn; `HOST`, `PORT`, `PUBLIC_URL` env vars control binding and the advertised card URL. `langchain_agent.py` and `foundry_*.py` reuse `agent_core.answer` with a different `chat` callable or hosting.
- The `Dockerfile` bakes the gold layer into the image by running `01_generate_data.py` and `04_medallion_delta.py` at build time.

## Config

Copy `.env.example` to `.env` (`setup.py` does this). `AGENT_SUMMARY=off` skips the second LLM call (useful on free-tier rate limits). `.env` holds keys and is gitignored.
