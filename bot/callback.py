from aiogram.filters.callback_data import CallbackData

from app.core.enums import MessageType, SpamType


class MainCallback(CallbackData, prefix="m"):
    action: str


class OrganizationCallback(CallbackData, prefix="org"):
    action: str
    id: int


class SpamCallback(CallbackData, prefix="spam"):
    type: SpamType


class ChatCallback(CallbackData, prefix="chat"):
    action: str
    chat_id: int = 0


class ThreadCallback(CallbackData, prefix="thread"):
    action: str
    chat_id: int
    thread_id: int = 0


class MessageCallback(CallbackData, prefix="msg"):
    action: str
    data: str | None = None
    type: MessageType | None = None
