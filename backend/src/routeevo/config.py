"""Paths, environment loading and the fixed run limits from docs/implementation-decisions.md."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
VAR_DIR = Path(os.environ.get("ROUTEEVO_VAR_DIR", BACKEND_DIR / "var"))
TASK_SPEC_DIR = BACKEND_DIR / "tasks"
TASK_DATA_DIR = VAR_DIR / "tasks"
RUNS_DIR = VAR_DIR / "runs"
DB_PATH = VAR_DIR / "routeevo.sqlite3"
RUN_LOCK_PATH = VAR_DIR / "run.lock"


def load_dotenv(path: Path = BACKEND_DIR / ".env") -> None:
    """Minimal KEY=VALUE loader. The project .env wins over the shell, which may carry unrelated values
    (e.g. OPENAI_API_KEY=ollama set for local tools)."""
    if not path.exists() or os.environ.get("ROUTEEVO_NO_DOTENV"):
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ[key.strip()] = value


@dataclass(frozen=True)
class RunLimits:
    max_model_requests: int = 6
    max_candidates: int = 4
    wall_clock_s: float = 300.0
    model_request_timeout_s: float = 120.0
    measurement_timeout_s: float = 10.0
    # Do not start a model request with less wall clock left than this.
    min_request_window_s: float = 15.0
    # None means no token budget (decision doc: no hard cost cap for now).
    token_budget: int | None = None
    max_code_bytes: int = 20_000

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MeasureConfig:
    repeats: int = 5
    cpus: float = 1.0
    memory: str = "1g"
    pids_limit: int = 64
    max_output_bytes: int = 64 * 1024 * 1024
    ready_timeout_s: float = 30.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModelConfig:
    provider: str  # "openai_responses" | "chat_compat" | "scripted"
    model: str
    role: str  # "small" | "large"
    base_url: str | None = None
    reasoning_effort: str | None = None
    enable_thinking: bool | None = None
    max_output_tokens: int = 4096
    temperature: float | None = None
    response_format: str = "json_schema"  # chat_compat: none | json_object | json_schema
    extra: dict = field(default_factory=dict)

    def public_dict(self) -> dict:
        """Configuration safe to persist (never includes credentials)."""
        return asdict(self)


def default_model_configs() -> dict[str, ModelConfig]:
    load_dotenv()
    thinking = os.environ.get("QWEN_ENABLE_THINKING")
    if thinking is not None and thinking.lower() not in ("true", "false"):
        raise ValueError("QWEN_ENABLE_THINKING must be true or false")
    small = ModelConfig(
        provider="chat_compat",
        role="small",
        model=os.environ.get("QWEN_MODEL", "qwen-unset"),
        base_url=os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:11434/v1"),
        # Thinking makes local Qwen latency unpredictable (89-172 s for one request); "none" keeps it ~10-15 s.
        reasoning_effort=os.environ.get("QWEN_REASONING_EFFORT") or None,
        enable_thinking=thinking.lower() == "true" if thinking is not None else None,
        max_output_tokens=int(os.environ.get("QWEN_MAX_OUTPUT_TOKENS", "8192")),
        temperature=float(os.environ["QWEN_TEMPERATURE"]) if os.environ.get("QWEN_TEMPERATURE") else None,
        response_format=os.environ.get("QWEN_RESPONSE_FORMAT", "none"),
    )
    large = ModelConfig(
        provider="openai_responses",
        role="large",
        model=os.environ.get("OPENAI_MODEL", "gpt-6.1-sol"),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "xhigh"),
        max_output_tokens=int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "32000")),
    )
    return {"small": small, "large": large}
