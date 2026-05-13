from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.models.base import Base


class ChatSettings(Base):
    __tablename__ = "chat_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chat_id: Mapped[UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    min_players: Mapped[int] = mapped_column(Integer, default=4, server_default="4")
    max_players: Mapped[int] = mapped_column(Integer, default=12, server_default="12")
    day_duration_sec: Mapped[int] = mapped_column(Integer, default=120, server_default="120")
    night_duration_sec: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    voting_duration_sec: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    delete_dead_messages: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    mute_night_chat: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
