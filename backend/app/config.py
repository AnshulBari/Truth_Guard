"""Runtime configuration, loaded from environment variables (optionally .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "truthguard.db"


def _load_env_file(path: Path) -> None:
    """Minimal .env loader so the app can run without extra dependencies."""
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# .env at the repo root and inside backend/ are both supported. Existing
# process environment variables always win.
_load_env_file(PROJECT_DIR / ".env")
_load_env_file(BACKEND_DIR / ".env")


@dataclass
class Settings:
    db_path: Path = DEFAULT_DB_PATH
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout: float = 60.0
    allowed_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    max_upload_mb: int = 20

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_key.strip())

    @property
    def provider(self) -> str:
        try:
            from urllib.parse import urlparse

            host = urlparse(self.llm_base_url).hostname or "custom"
        except Exception:  # pragma: no cover - defensive
            host = "custom"
        return host

    @property
    def mode(self) -> str:
        return "llm_assisted" if self.llm_configured else "deterministic"

    @property
    def mode_note(self) -> str:
        if self.llm_configured:
            return (
                f"LLM-assisted mode: synthesis and semantic critique use {self.llm_model} "
                f"via {self.provider}. Resolution and citation checks remain deterministic rules."
            )
        return (
            "Deterministic demo mode — no model API key is configured. The synthesizer is "
            "rule-based and semantic LLM critique is disabled. Conflicts are detected by "
            "numeric, metadata, supersession and scope checks. No LLM output is simulated."
        )

    @classmethod
    def from_env(cls) -> "Settings":
        raw_db = os.getenv("TRUTHGUARD_DB", "").strip()
        db_path = Path(raw_db).expanduser() if raw_db else DEFAULT_DB_PATH
        origins = [
            o.strip()
            for o in os.getenv(
                "TRUTHGUARD_CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if o.strip()
        ]
        try:
            timeout = float(os.getenv("LLM_TIMEOUT", "60"))
        except ValueError:
            timeout = 60.0
        try:
            max_upload = int(os.getenv("TRUTHGUARD_MAX_UPLOAD_MB", "20"))
        except ValueError:
            max_upload = 20
        return cls(
            db_path=db_path,
            llm_api_key=os.getenv("LLM_API_KEY") or None,
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            llm_timeout=timeout,
            allowed_origins=origins or ["http://localhost:3000"],
            max_upload_mb=max_upload,
        )
