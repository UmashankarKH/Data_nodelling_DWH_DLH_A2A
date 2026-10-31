# FreshKart lab: set up your own laptop (about 10 minutes)

By the end you will have a private Python environment, all the lab code, and a working connection to an open-source model. You do this once. After that, every lab is one command.

## 1. What you need

- **Python 3.10 or newer.** Check with `python --version` (on Windows try `py --version`). If it is older or missing, install it from python.org. On Windows, tick "Add Python to PATH" in the installer.
- About 2 GB of free disk space and an internet connection.
- **One free model key** from OpenRouter or NVIDIA (section 2). No card needed for either. If you do not want a key, you can use mock mode and still do every lab.

## 2. Pick how you will run the model (choose ONE)

| Option | You need | Choose it when |
| --- | --- | --- |
| **A. OpenRouter** | A free account and API key | You want the quickest start. Free models have low limits. |
| **B. NVIDIA** | A free developer account and API key | OpenRouter's free limits annoy you, or you want NVIDIA-hosted open models. |
| **C. Ollama** | A laptop with 16 GB RAM (or a GPU) | You want the model to run fully on your own machine, offline. |
| **D. Mock** | Nothing | The Wi-Fi is bad or you cannot sign up. Answers are canned for a few questions. |

### Option A: OpenRouter

1. Go to https://openrouter.ai and sign in (email or GitHub).
2. Open https://openrouter.ai/keys, click **Create key**, name it `fde-lab`, and copy the key. It starts with `sk-or-`.
3. Free models have ids that end in `:free`. They are rate limited. At the time of writing a new account gets roughly 20 requests a minute and about 50 a day on free models; check the OpenRouter FAQ for today's numbers. Each lab question uses 2 requests (see the tip in section 7 to use 1).

### Option B: NVIDIA

1. Go to https://build.nvidia.com and sign in with a free developer account.
2. Open any model card (for example Llama 3.3 70B Instruct) and click **Get API Key**. The key starts with `nvapi-`.
3. The free tier is rate limited too. The lab already points at NVIDIA's OpenAI-compatible endpoint for you.

### Option C: Ollama

1. Install Ollama from https://ollama.com.
2. Run `ollama pull qwen2.5-coder:7b` once (a few GB). If your laptop is small, use a smaller model and set `LLM_MODEL` in `.env`.

### Option D: Mock

Nothing to install. The setup script will offer it as choice 4.

## 3. Run the setup script

Unzip `fde_lab.zip`, open a terminal inside the `fde_lab` folder, and run:

```
python setup.py
```

On Windows, use `py setup.py` if `python` is not found. The script will:

1. create a private environment in a folder called `.venv`,
2. install every package the labs need,
3. ask which model option you chose and for your key (typing is hidden),
4. write a `.env` file and test the model connection.

You should end with `Packages OK` and, for a real model, `Your model connection works.`

No prompts wanted? These work too:

```
python setup.py --provider mock
python setup.py --provider ollama
```

For OpenRouter or NVIDIA, prefer the interactive prompt: a key typed on the command line stays in your shell history.

## 4. Switch the environment on

Do this in every new terminal you open inside the `fde_lab` folder.

| Your system | Command |
| --- | --- |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `.venv\Scripts\activate` |
| Mac or Linux | `source .venv/bin/activate` |

Your prompt now starts with `(.venv)`. If PowerShell says scripts are disabled, run `Set-ExecutionPolicy -Scope Process Bypass` once in that window and try again.

## 5. Test the model

```
python check_llm.py
```

Expected: `Reply: 'Model OK'` and `Your model connection works.`

To see which models your provider offers (free ones first on OpenRouter):

```
python check_llm.py --list
python check_llm.py --list coder
```

To change model or provider, edit `.env` (any text editor). For example:

```
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-...
LLM_MODEL=qwen/qwen2.5-coder-32b-instruct
```

Free model names change often. If you get "model not found", pick a current id from `--list`.

## 6. Run the labs

Always from the `fde_lab` folder with `(.venv)` showing.

| Lab | Command | What you learn |
| --- | --- | --- |
| 0 | `python 01_generate_data.py` | Creates the messy raw files in `raw/` |
| 1 | open the files in `raw/` and list the problems | Why raw data cannot be trusted |
| 2 | `python 02_star_schema.py` | Grain, facts, dimensions |
| 3 | `python 03_scd2_and_questions.py` | History with SCD Type 2, five business questions |
| 4 | `python 04_medallion_delta.py` | Bronze, silver, gold as Delta tables, time travel |
| 5 | Terminal 1: `python a2a_server.py` | Starts the A2A agent |
| 5 | Terminal 2 (activate `.venv` there too): `python a2a_client.py "What was net revenue by month?"` | Asks it a question over A2A |

After the server starts, open http://127.0.0.1:9999/.well-known/agent-card.json in a browser. That is the agent's business card.

You can also test the brain without A2A: `python agent_core.py "Top 5 products by revenue?"`

## 7. Optional: the LangChain version

LangChain is not needed for the labs. If you want to see the same agent written with it:

```
pip install langchain-openai
python langchain_agent.py "What was net revenue by month?"
```

It works with OpenRouter, NVIDIA and Ollama because they all speak the OpenAI API, so LangChain's `ChatOpenAI` only needs a different `base_url`.

**Tip for free tiers:** add `AGENT_SUMMARY=off` to `.env` to skip the second model call that writes the plain-English summary. You still get the numbers and the SQL.

## 8. If `setup.py` fails: do it by hand

```
python -m venv .venv
source .venv/bin/activate          (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env               (Windows: copy .env.example .env)
```

Then open `.env`, set `LLM_PROVIDER` and the matching key, and run `python check_llm.py`.

## 9. Troubleshooting

| What you see | Fix |
| --- | --- |
| `python` is not recognised | Use `py` on Windows, or `python3` on Mac and Linux. Reinstall Python and tick "Add to PATH". |
| `ModuleNotFoundError` | The environment is not on. Run the command from section 4. |
| `No API key found for provider ...` | Open `.env` and paste the key after the `=` sign, with no quotes or spaces. |
| `AuthenticationError` or 401 | The key is wrong or expired. Create a new one and paste it again. |
| `model not found` or 404 | Run `python check_llm.py --list` and copy a current id into `LLM_MODEL=`. |
| `RateLimitError` or 429 | You used up the free tier. Wait a minute, set `AGENT_SUMMARY=off`, or switch to `LLM_PROVIDER=mock`. |
| `Connection error` with Ollama | Start it with `ollama serve`, and check you ran `ollama pull`. |
| `Address already in use` (port 9999) | An old copy of the server is still running. Close it with Ctrl+C. |
| Lab 4 cannot rebuild `lakehouse/` on Windows | Close the folder in File Explorer, then rerun. |
| Answers are slow | Normal for the first call and for large models. Try a smaller model, or mock mode. |
| The model writes bad SQL | The agent retries once with the error. A bigger model helps. Try another id from `--list`. |

## 10. Keep your key safe

- Your key lives only in `.env`. That file is already listed in `.gitignore`, so it will not be uploaded to GitHub. Do not remove that line.
- Never paste your key into chat, screenshots or a shared document.
- If it leaks, delete the key on the provider's website and create a new one.
