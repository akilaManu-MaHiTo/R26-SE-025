"""Switch the LLM backend between local Ollama and a Colab-hosted Ollama.

Usage:
    python switch_llm.py status
    python switch_llm.py colab <base-url> [api-key]
    python switch_llm.py local
"""

import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"

LOCAL_BASE_URL = "http://localhost:11434"
LOCAL_MODEL = "qwen2.5:3b-instruct"
COLAB_MODEL = "qwen3:8b"

LLM_LINES = (
    "ENV",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "COLAB_MODEL",
    "OLLAMA_API_KEY",
)


def _line_for(key: str, value: str) -> str:
    return f"{key}={value}"


class SwitchableEnv:
    def __init__(self, env_path: Path):
        self.env_path = env_path

    def _load_lines(self) -> list[str]:
        if not self.env_path.exists():
            raise FileNotFoundError(f"missing .env file: {self.env_path}")
        return self.env_path.read_text(encoding="utf-8").splitlines()

    def _newline(self) -> str:
        raw = self.env_path.read_bytes()
        return "\r\n" if b"\r\n" in raw else "\n"

    def _rewrite(self, updates: dict[str, str]) -> None:
        lines = self._load_lines()
        newline = self._newline()
        seen: set[str] = set()
        out: list[str] = []
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line else None
            if key in updates:
                out.append(_line_for(key, updates[key]))
                seen.add(key)
            else:
                out.append(line)
        for key in LLM_LINES:
            if key not in seen:
                out.append(_line_for(key, updates.get(key, "")))
        text = newline.join(out) + newline
        self.env_path.write_bytes(text.encode("utf-8"))

    def set_colab(self, base_url: str, api_key: str | None) -> None:
        # v2 notebook (ngrok) has no API key — api_key may be None/empty, handle both
        # Always set COLAB_MODEL to qwen3:8b for colab, keep OLLAMA_MODEL for local fallback
        self._rewrite(
            {
                "ENV": "colab",
                "OLLAMA_BASE_URL": base_url.rstrip("/"),
                "OLLAMA_MODEL": LOCAL_MODEL,
                "COLAB_MODEL": COLAB_MODEL,
                "OLLAMA_API_KEY": api_key or "",
            }
        )

    def set_local(self) -> None:
        self._rewrite(
            {
                "ENV": "local",
                "OLLAMA_BASE_URL": LOCAL_BASE_URL,
                "OLLAMA_MODEL": LOCAL_MODEL,
                "COLAB_MODEL": COLAB_MODEL,
                "OLLAMA_API_KEY": "",
            }
        )

    def values(self) -> dict[str, str]:
        result = {}
        for line in self._load_lines():
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()
        return result


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        env = SwitchableEnv(ENV_PATH)
        command = args[0] if args else ""
        if command == "status":
            values = env.values()
            run_env = values.get("ENV") or "local"
            if run_env == "colab":
                base_url = values.get("OLLAMA_BASE_URL", "")
                model = values.get("COLAB_MODEL") or values.get("OLLAMA_MODEL") or COLAB_MODEL
                # detect tunnel type for v2 docs
                tunnel = "ngrok" if "ngrok" in base_url else "cloudflared" if "trycloudflare" in base_url else "custom"
                print(f"ENV={run_env} ({tunnel})")
                print(f"LLM_BASE_URL={base_url}")
                print(f"LLM_MODEL={model}")
                api_key = values.get('OLLAMA_API_KEY','')
                print(f"OLLAMA_API_KEY={'(empty, ngrok v2)' if not api_key else api_key[:6]+'...'}")
                # v2 hint
                if "ngrok" in base_url and not api_key:
                    print("note: v2 ngrok needs no API key (colab_ollama_v2.ipynb)")
                return 0
            else:
                base_url = LOCAL_BASE_URL
                model = values.get("OLLAMA_MODEL") or LOCAL_MODEL
                print(f"ENV={run_env}")
                print(f"LLM_BASE_URL={base_url}")
                print(f"LLM_MODEL={model}")
                print(f"OLLAMA_API_KEY={values.get('OLLAMA_API_KEY', '')}")
                return 0
        if command == "colab":
            if len(args) < 2:
                print("usage: python switch_llm.py colab <base-url> [api-key]")
                print("  v1 (cloudflared): python switch_llm.py colab https://xxx.trycloudflare.com <api-key>")
                print("  v2 (ngrok):       python switch_llm.py colab https://xxx.ngrok-free.app")
                print("                    (v2 colab_ollama_v2.ipynb prints only OLLAMA_BASE_URL, no key needed)")
                return 1
            # handle v2: base_url may be ngrok-free.app or ngrok.app, no key
            base_url = args[1]
            api_key = args[2] if len(args) > 2 else ""
            # support `python switch_llm.py colab <url>` for v2
            if base_url.startswith("https://") and "ngrok" in base_url and not api_key:
                print("detected v2 ngrok URL (no API key)")
            env.set_colab(base_url, api_key)
            vals = env.values()
            print(f"switched to colab: {vals['OLLAMA_BASE_URL']} model={vals.get('COLAB_MODEL', COLAB_MODEL)}")
            return 0
        if command == "local":
            env.set_local()
            print("switched to local: " + env.values()["OLLAMA_BASE_URL"])
            return 0
        print(__doc__.strip())
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
