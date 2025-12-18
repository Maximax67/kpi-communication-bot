from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat_captain import ChatCaptain


async def get_captain(
    db: AsyncSession,
    organization_id: int,
    user_id: int | None = None,
    username: str | None = None,
) -> ChatCaptain | None:
    if user_id is None and username is None:
        raise ValueError("At least one param should be provided: user_id, username")

    conditions = [ChatCaptain.organization_id == organization_id]
    or_conditions = []

    if user_id is not None:
        or_conditions.append(ChatCaptain.connected_user_id == user_id)

    if username is not None:
        or_conditions.append(ChatCaptain.validated_username == username)

    if or_conditions:
        if len(or_conditions) == 1:
            conditions.append(or_conditions[0])
        else:
            conditions.append(or_(*or_conditions))

    q = select(ChatCaptain).where(*conditions).limit(1)
    result = await db.execute(q)

    return result.scalar_one_or_none()
