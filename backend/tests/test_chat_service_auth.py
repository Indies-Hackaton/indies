import tempfile
import unittest
from pathlib import Path

from app.core.database import (
    ConversationRecord,
    init_db,
    make_engine,
    make_sessionmaker,
)
from app.services.chat_service import ChatNotFoundError, ChatService


class ChatServiceAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_conversation_can_be_continued_by_same_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "indies-test.db"
            engine = make_engine(f"sqlite+aiosqlite:///{db_path}")

            try:
                await init_db(engine)
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

                    service = ChatService(
                        session=session,
                        minimax=None,  # type: ignore[arg-type]
                        mercado_publico=None,  # type: ignore[arg-type]
                        senado=None,  # type: ignore[arg-type]
                        contraloria=None,  # type: ignore[arg-type]
                        camara=None,  # type: ignore[arg-type]
                    )

                    conversation = await service._get_or_create_conversation(
                        conversation_id="conversation-1",
                        first_message="Sigue con esta consulta",
                        user_id="user_123",
                    )

                    self.assertEqual(conversation.id, "conversation-1")
            finally:
                await engine.dispose()

    async def test_owned_conversation_cannot_be_continued_by_other_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "indies-test.db"
            engine = make_engine(f"sqlite+aiosqlite:///{db_path}")

            try:
                await init_db(engine)
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

                    service = ChatService(
                        session=session,
                        minimax=None,  # type: ignore[arg-type]
                        mercado_publico=None,  # type: ignore[arg-type]
                        senado=None,  # type: ignore[arg-type]
                        contraloria=None,  # type: ignore[arg-type]
                        camara=None,  # type: ignore[arg-type]
                    )

                    with self.assertRaises(ChatNotFoundError):
                        await service._get_or_create_conversation(
                            conversation_id="conversation-1",
                            first_message="Sigue con esta consulta",
                            user_id="user_456",
                        )
            finally:
                await engine.dispose()


if __name__ == "__main__":
    unittest.main()
