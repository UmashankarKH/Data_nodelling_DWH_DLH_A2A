"""One tiny LLM wrapper for the whole lab.

It talks to ANY OpenAI-compatible endpoint. You pick the provider with ONE line in your .env file:

    LLM_PROVIDER=openrouter   free open models through OpenRouter      (needs OPENROUTER_API_KEY)
    LLM_PROVIDER=nvidia       open models on build.nvidia.com          (needs NVIDIA_API_KEY)
    LLM_PROVIDER=ollama       a model running on your own laptop       (no key)
    LLM_PROVIDER=azure        a model deployed in Microsoft Foundry    (needs AZURE_OPENAI_* values)
    LLM_PROVIDER=mock         no model at all, canned SQL              (works offline)

Any value can be overridden: LLM_MODEL, LLM_BASE_URL, LLM_API_KEY, LLM_API (chat or responses).
"""
import os
import re
from types import SimpleNamespace

try:
    from dotenv import load_dotenv
    load_dotenv()                      # reads the .env file next to the scripts, if there is one
except ImportError:                    # python-dotenv is optional
    pass

KEY_HELP = {
    "OPENROUTER_API_KEY": "Create a free key at https://openrouter.ai/keys",
    "NVIDIA_API_KEY": "Create a free key at https://build.nvidia.com (open any model, click Get API Key)",
    "AZURE_OPENAI_API_KEY": "Copy the key from your Foundry resource in the Azure portal",
}


def settings() -> SimpleNamespace:
    """Work out provider, endpoint, key and model from environment variables."""
    provider = (os.getenv("LLM_PROVIDER")
                or ("mock" if os.getenv("LLM_MODE") == "mock" else "ollama")).strip().lower()
    presets = {
        "ollama": dict(base_url="http://localhost:11434/v1", key_env=None,
                       model="qwen2.5-coder:7b", api="chat"),
        "openrouter": dict(base_url="https://openrouter.ai/api/v1", key_env="OPENROUTER_API_KEY",
                           model="meta-llama/llama-3.3-70b-instruct:free", api="chat"),
        "nvidia": dict(base_url="https://integrate.api.nvidia.com/v1", key_env="NVIDIA_API_KEY",
                       model="meta/llama-3.3-70b-instruct", api="chat"),
        "azure": dict(base_url=os.getenv("AZURE_OPENAI_BASE_URL"), key_env="AZURE_OPENAI_API_KEY",
                      model=os.getenv("AZURE_OPENAI_DEPLOYMENT"), api="responses"),
    }
    if provider == "mock":
        return SimpleNamespace(provider="mock", base_url="", api_key="", model="mock", api="chat")
    if provider not in presets:
        raise RuntimeError(f"Unknown LLM_PROVIDER '{provider}'. Use one of: {', '.join(list(presets) + ['mock'])}.")
    p = presets[provider]
    key_env = p["key_env"]
    api_key = os.getenv("LLM_API_KEY") or (os.getenv(key_env) if key_env else None) or ("ollama" if provider == "ollama" else None)
    s = SimpleNamespace(
        provider=provider,
        base_url=os.getenv("LLM_BASE_URL") or p["base_url"],
        api_key=api_key,
        model=os.getenv("LLM_MODEL") or p["model"],
        api=os.getenv("LLM_API") or p["api"],
    )
    if not s.api_key:
        raise RuntimeError(f"No API key found for provider '{provider}'. Add {key_env}=... to your .env file. "
                           f"{KEY_HELP.get(key_env, '')}")
    if not s.base_url or not s.model:
        raise RuntimeError(f"Provider '{provider}' needs AZURE_OPENAI_BASE_URL and AZURE_OPENAI_DEPLOYMENT in .env.")
    return s


def chat(system: str, user: str, role: str = "sql") -> str:
    s = settings()
    if s.provider == "mock":
        return _mock(user, role)
    from openai import OpenAI
    client = OpenAI(base_url=s.base_url, api_key=s.api_key, timeout=180, max_retries=4)   # retries help on free tiers
    if s.api == "responses":
        text = client.responses.create(model=s.model, instructions=system, input=user).output_text or ""
    else:
        r = client.chat.completions.create(
            model=s.model, temperature=0,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        text = r.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()   # some open models print their reasoning


def _mock(user: str, role: str) -> str:
    if role == "summary":
        return "(mock mode - no model used) Here are the numbers returned by the query."
    q = user.lower()
    if "month" in q:
        return ("SELECT d.month_name, ROUND(SUM(f.net_amount), 0) AS revenue FROM fact_sales f "
                "JOIN dim_date d ON d.date_key = f.date_key GROUP BY d.month, d.month_name ORDER BY d.month")
    if "product" in q:
        return ("SELECT p.product_name, ROUND(SUM(f.net_amount), 0) AS revenue FROM fact_sales f "
                "JOIN dim_product p ON p.product_key = f.product_key GROUP BY p.product_name ORDER BY revenue DESC LIMIT 5")
    if "city" in q:
        return ("SELECT c.city, ROUND(SUM(f.net_amount), 0) AS revenue FROM fact_sales f "
                "JOIN dim_customer c ON c.customer_key = f.customer_key GROUP BY c.city ORDER BY revenue DESC")
    if "web" in q or "store" in q:
        return "SELECT source, ROUND(SUM(net_amount), 0) AS revenue FROM fact_sales GROUP BY source"
    return "SELECT ROUND(SUM(net_amount), 0) AS revenue FROM fact_sales"
