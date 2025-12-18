from aiogram.types import Message
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization


async def get_organization_from_message(
    db: AsyncSession, message: Message
) -> Organization | None:
    if message.from_user is None:
        return None

    organization_stmt = (
        select(Organization)
        .options(joinedload(Organization.bot))
        .where(
            or_(
                Organization.admin_chat_id == message.chat.id,
                Organization.owner == message.from_user.id,
            )
        )
        .order_by((Organization.admin_chat_id == message.chat.id).desc())
        .limit(1)
    )
    organization_result = await db.execute(organization_stmt)
    organization = organization_result.scalar_one_or_none()

    return organization
