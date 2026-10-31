# FreshKart lab: data modeling, warehouse, lakehouse, and an A2A agent on top

Everything runs on a laptop. **Start with SETUP.md**: it walks you through the one-command setup, getting a free OpenRouter or NVIDIA key, and troubleshooting.

```
python setup.py          (Windows: py setup.py)
```

## Files

| File | Purpose |
| --- | --- |
| `SETUP.md` | Learner setup guide |
| `setup.py` | One-command setup (environment, packages, `.env`, model test) |
| `check_llm.py` | Test your model connection, or `--list` the models your provider offers |
| `01_generate_data.py` ... `05_export_gold_for_azure.py` | Labs 0 to 4 and the Azure export helper |
| `agent_core.py`, `llm.py` | The agent brain and the model wrapper (OpenRouter, NVIDIA, Ollama, Azure, mock) |
| `a2a_server.py`, `a2a_client.py` | Lab 5: the A2A agent and a caller |
| `langchain_agent.py` | Optional LangChain version of the agent brain |
| `FOUNDRY_DEMO.md`, `Dockerfile`, `foundry_*.py`, `requirements-extras.txt` | Trainer's Microsoft Foundry demo (not for learners) |

## Run order

| Step | Command |
| --- | --- |
| Lab 0 | `python 01_generate_data.py` |
| Lab 1 | open `raw/` and find the problems |
| Lab 2 | `python 02_star_schema.py` |
| Lab 3 | `python 03_scd2_and_questions.py` |
| Lab 4 | `python 04_medallion_delta.py` |
| Lab 5 | `python a2a_server.py`, then in a second terminal `python a2a_client.py "revenue by month"` |

Tested with: Python 3.13, duckdb 2.0, deltalake 1.6, a2a-sdk 1.3, openai 3.x. The Foundry and Container Apps parts were not run against Azure; see FOUNDRY_DEMO.md.
