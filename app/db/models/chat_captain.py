from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.timestamps import TimestampMixin


if TYPE_CHECKING:
    from app.db.models.organization import Organization
    from app.db.models.user import User
    from app.db.models.chat import Chat


class ChatCaptain(Base, TimestampMixin):
    __tablename__ = "chat_captains"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validated_username: Mapped[str] = mapped_column(String(32), nullable=False)
    chat_title: Mapped[str] = mapped_column(String(32), nullable=False)

    connected_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    connected_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("chats.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )

    is_bot_blocked: Mapped[bool] = mapped_column(default=True, nullable=False)

    organization: Mapped["Organization"] = relationship(
        back_populates="captains", uselist=False
    )
    connected_user: Mapped["User | None"] = relationship(
        back_populates="chats_captain", uselist=False
    )
    chat: Mapped["Chat | None"] = relationship(back_populates="captains", uselist=False)
