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
        self._rewrite(
            {
                "ENV": "colab",
                "OLLAMA_BASE_URL": base_url,
                "OLLAMA_MODEL": LOCAL_MODEL,
                "OLLAMA_API_KEY": api_key or "",
            }
        )

    def set_local(self) -> None:
        self._rewrite(
            {
                "ENV": "local",
                "OLLAMA_BASE_URL": LOCAL_BASE_URL,
                "OLLAMA_MODEL": LOCAL_MODEL,
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
                model = values.get("COLAB_MODEL") or COLAB_MODEL
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
                return 1
            env.set_colab(args[1], args[2] if len(args) > 2 else None)
            print("switched to colab: " + env.values()["OLLAMA_BASE_URL"])
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
