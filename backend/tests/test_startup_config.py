import unittest

from app.core.config import Settings
from app.services.contraloria import normalize_asyncpg_dsn


def _settings(**overrides: str | None) -> Settings:
    values = {
        "MINIMAX_API_KEY": "test-key",
        "MINIMAX_BASE_URL": "https://example.test/v1",
        "MINIMAX_MODEL": "test-model",
        "MERCADO_PUBLICO_TICKET": "test-ticket",
        "MERCADO_PUBLICO_BASE_URL": "https://example.test/mp",
        "FRONTEND_ORIGINS": "http://localhost:3000",
    }
    values.update(overrides)
    return Settings(**values)


class StartupConfigTests(unittest.TestCase):
    def test_sqlite_database_does_not_configure_contraloria(self) -> None:
        settings = _settings(DATABASE_URL="sqlite+aiosqlite:///./data/indies.db")

        self.assertIsNone(settings.resolved_contraloria_database_url)

    def test_postgres_database_can_back_contraloria_by_default(self) -> None:
        settings = _settings(DATABASE_URL="postgresql://user:pass@example.test/db")

        self.assertEqual(
            settings.resolved_contraloria_database_url,
            "postgresql://user:pass@example.test/db",
        )

    def test_explicit_contraloria_url_takes_precedence(self) -> None:
        settings = _settings(
            DATABASE_URL="sqlite+aiosqlite:///./data/indies.db",
            CONTRALORIA_DATABASE_URL="postgres://user:pass@example.test/contraloria",
        )

        self.assertEqual(
            settings.resolved_contraloria_database_url,
            "postgres://user:pass@example.test/contraloria",
        )

    def test_asyncpg_dsn_normalizes_sqlalchemy_url_and_neon_params(self) -> None:
        dsn = normalize_asyncpg_dsn(
            "postgresql+asyncpg://user:pass@example.test/db"
            "?sslmode=require&channel_binding=require&connect_timeout=10"
        )

        self.assertEqual(
            dsn,
            "postgresql://user:pass@example.test/db?connect_timeout=10",
        )


if __name__ == "__main__":
    unittest.main()
