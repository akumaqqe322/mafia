from uuid import UUID

from sqlalchemy import select

from app.infrastructure.models.chat_settings import ChatSettings
from app.infrastructure.repositories.base import BaseRepository


class ChatSettingsRepository(BaseRepository[ChatSettings]):
    async def get_by_chat_id(self, chat_id: UUID) -> ChatSettings | None:
        stmt = select(ChatSettings).where(ChatSettings.chat_id == chat_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_default_for_chat(self, chat_id: UUID) -> ChatSettings:
        settings = ChatSettings(chat_id=chat_id)
        self.session.add(settings)
        await self.session.flush()
        return settings

    async def get_or_create_default(self, chat_id: UUID) -> ChatSettings:
        settings = await self.get_by_chat_id(chat_id)
        if settings:
            return settings
        return await self.create_default_for_chat(chat_id)
