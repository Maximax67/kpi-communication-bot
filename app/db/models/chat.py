from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.enums import ChatType, VisibilityLevel
from app.db.base import Base
from app.db.timestamps import TimestampMixin


if TYPE_CHECKING:
    from app.db.models.organization import Organization
    from app.db.models.chat_thread import ChatThread
    from app.db.models.chat_captain import ChatCaptain
    from app.db.models.chat_user import ChatUser


class Chat(Base, TimestampMixin):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[ChatType] = mapped_column(
        Enum(ChatType, name="chat_type"),
        nullable=False,
    )
    visibility_level: Mapped[VisibilityLevel] = mapped_column(
        Enum(VisibilityLevel, name="visibility_level"),
        nullable=False,
    )
    captain_connected_thread: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    pin_requests: Mapped[bool] = mapped_column(default=False, nullable=False)
    tag_on_requests: Mapped[str | None] = mapped_column(nullable=True)

    organization: Mapped["Organization"] = relationship(
        back_populates="chats", uselist=False
    )
    threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="chat", passive_deletes=True
    )
    captains: Mapped[list["ChatCaptain"]] = relationship(
        back_populates="chat", passive_deletes=True
    )
    users: Mapped[list["ChatUser"]] = relationship(
        back_populates="chat", passive_deletes=True
    )
