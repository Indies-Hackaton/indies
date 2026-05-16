"""Application configuration.

All runtime configuration is centralised here and loaded from environment
variables (or a local ``.env`` file) through Pydantic's settings management.
Importing :func:`get_settings` anywhere in the app yields a single cached,
strongly-typed :class:`Settings` instance.
"""

from functools import lru_cache

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
    # Base URL of the MiniMax API; defaults to the official global endpoint.
    MINIMAX_BASE_URL: str = "https://api.minimax.io/v1"
    # Chat model used as the intent router/classifier.
    MINIMAX_MODEL: str = "MiniMax-Text-01"

    # --- Mercado Publico (Chilean government procurement API) --------------
    # Ticket (token) required by every Mercado Publico request.
    MERCADO_PUBLICO_TICKET: str
    # Base URL for the public v1 services of Mercado Publico.
    MERCADO_PUBLICO_BASE_URL: str = (
        "https://api.mercadopublico.cl/servicios/v1/publico"
    )

    # --- CORS --------------------------------------------------------------
    # Comma-separated list of origins allowed to call this API.
    FRONTEND_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def allowed_origins(self) -> list[str]:
        """Return ``FRONTEND_ORIGINS`` as a clean list of origin strings."""
        return [
            origin.strip()
            for origin in self.FRONTEND_ORIGINS.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance.

    The :func:`lru_cache` decorator turns this into a lazy singleton so the
    ``.env`` file is parsed only once per process.
    """
    return Settings()
