import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect, select

from app.core.database import (
    ConversationRecord,
    init_db,
    make_engine,
    make_sessionmaker,
)


class DatabaseMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_schema_includes_conversation_user_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "indies-test.db"
            engine = make_engine(f"sqlite+aiosqlite:///{db_path}")

            try:
                await init_db(engine)

                async with engine.begin() as conn:
                    columns = await conn.run_sync(
                        lambda sync_conn: {
                            column["name"]
                            for column in inspect(sync_conn).get_columns(
                                "conversations"
                            )
                        }
                    )
                    indexes = await conn.run_sync(
                        lambda sync_conn: {
                            index["name"]
                            for index in inspect(sync_conn).get_indexes(
                                "conversations"
                            )
                        }
                    )

                self.assertIn("user_id", columns)
                self.assertIn("ix_conversations_user_id", indexes)

                sessionmaker = make_sessionmaker(engine)
                async with sessionmaker() as session:
                    session.add(
                        ConversationRecord(
                            id="conversation-1",
                            title="Test conversation",
                            user_id="user_123",
                        )
                    )
                    await session.commit()

                    stored_user_id = await session.scalar(
                        select(ConversationRecord.user_id).where(
                            ConversationRecord.id == "conversation-1"
                        )
                    )

                self.assertEqual(stored_user_id, "user_123")
            finally:
                await engine.dispose()


if __name__ == "__main__":
    unittest.main()
