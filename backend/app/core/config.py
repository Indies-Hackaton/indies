"""Application configuration.

All runtime configuration is centralised here and loaded from environment
variables (or a local ``.env`` file) through Pydantic's settings management.
Importing :func:`get_settings` anywhere in the app yields a single cached,
strongly-typed :class:`Settings` instance.
"""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Each attribute maps (case-insensitively) to an environment variable of the
    same name. Attributes without a default are *required*: the app will fail
    fast at startup if they are missing, which is the desired behaviour for
    credentials.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- MiniMax LLM -------------------------------------------------------
    # API key used to authenticate against the MiniMax reasoning engine.
    MINIMAX_API_KEY: str
    # Base URL of the MiniMax API.
    MINIMAX_BASE_URL: str
    # Model used by the planner/API-routing agent.
    MINIMAX_MODEL: str
    # Model used for human-facing chat responses. Falls back to MINIMAX_MODEL.
    MINIMAX_CHAT_MODEL: str | None = None

    # --- Mercado Publico (Chilean government procurement API) --------------
    # Ticket (token) required by every Mercado Publico request.
    MERCADO_PUBLICO_TICKET: str
    # Base URL for the public v1 services of Mercado Publico.
    MERCADO_PUBLICO_BASE_URL: str

    # --- CORS --------------------------------------------------------------
    # Comma-separated list of origins allowed to call this API.
    FRONTEND_ORIGINS: str

    # --- Persistence -------------------------------------------------------
    # SQLite is the default local store for conversations/messages/tool traces.
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/indies.db"

    @property
    def allowed_origins(self) -> list[str]:
        """Return ``FRONTEND_ORIGINS`` as a clean list of origin strings."""
        return [
            _normalise_origin(origin)
            for origin in self.FRONTEND_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def minimax_chat_model(self) -> str:
        """Return the chat model, falling back to the planner model."""
        return self.MINIMAX_CHAT_MODEL or self.MINIMAX_MODEL


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance.

    The :func:`lru_cache` decorator turns this into a lazy singleton so the
    ``.env`` file is parsed only once per process.
    """
    return Settings()


def _normalise_origin(origin: str) -> str:
    """Convert a full URL or trailing-slash URL into a CORS origin."""
    cleaned = origin.strip()
    parsed = urlsplit(cleaned)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return cleaned.rstrip("/")
