from sqlalchemy import select
from app.infrastructure.models.chat import Chat
from app.infrastructure.repositories.base import BaseRepository


class ChatRepository(BaseRepository[Chat]):
    async def get_by_telegram_chat_id(self, telegram_chat_id: int) -> Chat | None:
        stmt = select(Chat).where(Chat.telegram_chat_id == telegram_chat_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_chat_id: int,
        title: str | None = None,
        type: str = "group",
    ) -> Chat:
        chat = Chat(
            telegram_chat_id=telegram_chat_id,
            title=title,
            type=type,
        )
        self.session.add(chat)
        await self.session.flush()
        return chat

    async def get_or_create(
        self,
        telegram_chat_id: int,
        title: str | None = None,
        type: str = "group",
    ) -> Chat:
        chat = await self.get_by_telegram_chat_id(telegram_chat_id)
        if chat:
            chat.title = title
            chat.type = type
            return chat
        return await self.create(telegram_chat_id, title, type)
