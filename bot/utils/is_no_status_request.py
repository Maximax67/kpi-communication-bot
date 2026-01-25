from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MessageStatus, MessageType
from app.db.models.message import Message as MessageDB


async def is_no_status_request(
    db: AsyncSession, message: Message, destination_chat_id: int
) -> bool:
    last_request_stmt = (
        select(MessageDB.status)
        .where(
            MessageDB.chat_id == message.chat.id,
            MessageDB.destination_chat_id == destination_chat_id,
            MessageDB.type == MessageType.SERVICE,
            MessageDB.status.is_not(None),
        )
        .order_by(MessageDB.created_at.desc())
        .limit(1)
    )
    last_request_result = await db.execute(last_request_stmt)
    last_request_status = last_request_result.scalar_one_or_none()

    return last_request_status == MessageStatus.NEW
