"""Test your model connection, or list the models your provider offers.

    python check_llm.py                 test the model chosen in .env
    python check_llm.py --list          list model ids (free ones first on OpenRouter)
    python check_llm.py --list coder    list only ids containing the word 'coder'
"""
import sys
import time

import llm


def hint(e: Exception, s) -> str:
    import openai
    if isinstance(e, openai.AuthenticationError):
        return "The provider rejected your key. Re-copy it into .env (no quotes, no spaces)."
    if isinstance(e, openai.NotFoundError):
        return ("That model id was not found. Run `python check_llm.py --list` and put a valid id in .env "
                "as LLM_MODEL=... (free model names change often).")
    if isinstance(e, openai.RateLimitError):
        return "Rate limit hit (free tiers allow only a few requests). Wait a minute, or use LLM_PROVIDER=mock."
    if isinstance(e, openai.APIConnectionError):
        extra = " Is Ollama running? Try `ollama serve`." if s.provider == "ollama" else " Check your internet or the base URL."
        return f"Could not reach {s.base_url}.{extra}"
    return "Unexpected error. Read the message above and check your .env values."


def list_models(s, needle: str = "") -> None:
    import httpx
    headers = {"Authorization": f"Bearer {s.api_key}"} if s.api_key else {}
    r = httpx.get(f"{s.base_url.rstrip('/')}/models", headers=headers, timeout=30)
    r.raise_for_status()
    ids = sorted(m["id"] for m in r.json().get("data", []))
    if needle:
        ids = [i for i in ids if needle.lower() in i.lower()]
    if s.provider == "openrouter":
        ids = sorted(ids, key=lambda i: (not i.endswith(":free"), i))     # free models first
    print(f"{len(ids)} models from {s.base_url}" + (" (free ones first)" if s.provider == "openrouter" else ""))
    for i in ids[:80]:
        print("  ", i)
    if len(ids) > 80:
        print(f"   ... and {len(ids) - 80} more. Add a word to filter, e.g. --list llama")


def main() -> int:
    try:
        s = llm.settings()
    except RuntimeError as e:
        print("Setup problem:", e)
        return 1
    print(f"Provider: {s.provider} | model: {s.model} | endpoint: {s.base_url or '(none, mock mode)'}")
    if "--list" in sys.argv:
        if s.provider == "mock":
            print("Mock mode has no models to list.")
            return 0
        rest = [a for a in sys.argv[1:] if a != "--list"]
        list_models(s, rest[0] if rest else "")
        return 0
    t = time.time()
    try:
        answer = llm.chat("You are terse.", "Reply with exactly: model OK", role="summary")
    except Exception as e:
        print("FAILED:", type(e).__name__, "-", str(e)[:300])
        print("Hint:", hint(e, s))
        return 1
    print(f"Reply: {answer!r}  ({time.time() - t:.1f}s)")
    print("Your model connection works." if s.provider != "mock" else "Mock mode is on: fine for the labs, no model used.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
