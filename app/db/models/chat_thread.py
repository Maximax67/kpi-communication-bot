from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.enums import VisibilityLevel
from app.db.base import Base
from app.db.timestamps import TimestampMixin


if TYPE_CHECKING:
    from app.db.models.chat import Chat


class ChatThread(Base, TimestampMixin):
    __tablename__ = "chat_threads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chats.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(32), nullable=False)
    visibility_level: Mapped[VisibilityLevel] = mapped_column(
        Enum(VisibilityLevel, name="visibility_level"),
        nullable=False,
    )
    pin_requests: Mapped[bool] = mapped_column(default=False, nullable=False)
    tag_on_requests: Mapped[str | None] = mapped_column(nullable=True)

    chat: Mapped["Chat"] = relationship(back_populates="threads", uselist=False)
