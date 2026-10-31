"""One-command setup for the FreshKart lab. Works on Windows, Mac and Linux.

    python setup.py                      interactive: asks which model provider you want (Windows: py setup.py)
    python setup.py --provider mock      no questions, no key, works offline
    python setup.py --skip-install       only (re)write the .env file

What it does: creates a private Python environment in .venv, installs the packages,
writes your .env file (your key stays on your laptop), and tests the model connection.
"""
import argparse
import getpass
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
IS_WIN = os.name == "nt"
VPY = VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")

# choice -> (provider, key variable, where to get the key, default model)
PROVIDERS = {
    "1": ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/keys", "meta-llama/llama-3.3-70b-instruct:free"),
    "2": ("nvidia", "NVIDIA_API_KEY", "https://build.nvidia.com (open any model, click Get API Key)", "meta/llama-3.3-70b-instruct"),
    "3": ("ollama", None, "install Ollama from https://ollama.com, then run: ollama pull qwen2.5-coder:7b", "qwen2.5-coder:7b"),
    "4": ("mock", None, "no model, canned answers (fine for every lab)", ""),
}


def step(msg: str) -> None:
    print(f"\n==> {msg}")


def make_env(args) -> None:
    env_file = ROOT / ".env"
    if env_file.exists() and not args.force:
        print(".env already exists, keeping it. (Use --force to rewrite it.)")
        return
    interactive = sys.stdin.isatty() and not args.provider
    if args.provider:
        choice = next((k for k, v in PROVIDERS.items() if v[0] == args.provider), None)
        if not choice:
            sys.exit(f"Unknown provider '{args.provider}'. Use openrouter, nvidia, ollama or mock.")
    elif interactive:
        print("Which model do you want to use?")
        print("  1) OpenRouter  - free open models, needs a free key")
        print("  2) NVIDIA      - open models on build.nvidia.com, needs a free key")
        print("  3) Ollama      - a model running on your laptop, no key")
        print("  4) Mock        - no model at all, works offline")
        choice = input("Type 1, 2, 3 or 4 [1]: ").strip() or "1"
        if choice not in PROVIDERS:
            sys.exit("Please run setup again and type 1, 2, 3 or 4.")
    else:
        choice = "4"
        print("No terminal to ask questions, so using mock mode. Re-run with --provider to change.")
    provider, key_var, where, default_model = PROVIDERS[choice]
    lines = [f"LLM_PROVIDER={provider}"]
    if key_var:
        key = args.key or os.getenv(key_var, "")
        if not key and interactive:
            print(f"\nGet your free key here: {where}")
            key = getpass.getpass(f"Paste your {key_var} (typing is hidden, Enter to skip for now): ").strip()
        if not key:
            print(f"No key entered. Add it later to .env as {key_var}=... ({where})")
        lines.append(f"{key_var}={key}")
    elif provider == "ollama":
        print(f"\nReminder: {where}")
    if default_model and interactive:
        model = input(f"Model id, press Enter for {default_model}: ").strip()
        if model:
            lines.append(f"LLM_MODEL={model}")
    env_file.write_text("\n".join(lines) + "\n")
    if not IS_WIN:
        env_file.chmod(0o600)                 # only you can read it
    print(f"Wrote {env_file.name} (never share or upload this file).")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=["openrouter", "nvidia", "ollama", "mock"])
    ap.add_argument("--key", help="API key (otherwise it is read from the environment or asked)")
    ap.add_argument("--skip-install", action="store_true")
    ap.add_argument("--no-check", action="store_true", help="do not test the model at the end")
    ap.add_argument("--force", action="store_true", help="rewrite an existing .env")
    args = ap.parse_args()

    if sys.version_info < (3, 10):
        sys.exit(f"Python 3.10 or newer is needed (you have {sys.version.split()[0]}). Install it from python.org.")

    if not args.skip_install:
        step("Creating a private Python environment in .venv")
        if not VPY.exists():
            venv.create(VENV, with_pip=True)
        step("Installing packages (a few minutes the first time)")
        subprocess.check_call([str(VPY), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                               "-r", str(ROOT / "requirements.txt")])
        subprocess.check_call([str(VPY), "-c", "import duckdb, deltalake, pyarrow, openai, httpx, a2a; print('Packages OK')"])

    step("Setting up your model connection")
    make_env(args)

    if not args.no_check and VPY.exists():
        step("Testing the model connection")
        rc = subprocess.call([str(VPY), str(ROOT / "check_llm.py")], cwd=ROOT)
        if rc != 0:
            print("\nSetup finished, but the model test failed. Fix .env, then run: python check_llm.py")

    activate = r".venv\Scripts\activate" if IS_WIN else "source .venv/bin/activate"
    print(f"""
All set. Next, every time you open a new terminal in this folder:
    {activate}
Then start the labs:
    python 01_generate_data.py
See SETUP.md for the full lab order and troubleshooting.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
