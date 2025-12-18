from sqlalchemy import BigInteger, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.enums import MessageStatus, MessageType
from app.db.base import Base
from app.db.timestamps import TimestampMixin


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_message", "chat_id", "message_id"),
        Index(
            "ix_messages_destination_chat_message",
            "destination_chat_id",
            "destination_message_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    destination_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    destination_thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    destination_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    is_within_organization: Mapped[bool] = mapped_column(nullable=False)
    text: Mapped[str | None] = mapped_column(nullable=True)

    type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type"),
        nullable=False,
    )
    status: Mapped[MessageStatus | None] = mapped_column(
        Enum(MessageStatus, name="message_status"),
        nullable=True,
    )
    status_changed_by_user: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    is_status_reference: Mapped[bool | None] = mapped_column(nullable=True)
