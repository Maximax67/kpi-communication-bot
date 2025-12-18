from app.core.enums import MessageStatus
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.callback import MessageCallback


STATUS_EMOJI = {
    MessageStatus.NEW.value: "🔴",
    MessageStatus.IN_PROCESS.value: "🟡",
    MessageStatus.COMPLETED.value: "🟢",
}

STATUS_LABELS = {
    MessageStatus.NEW.value: "Не оброблено",
    MessageStatus.IN_PROCESS.value: "У роботі",
    MessageStatus.COMPLETED.value: "Виконано",
}


def get_status_emoji(status: MessageStatus | str) -> str:
    return STATUS_EMOJI.get(status, "❓")


def get_status_label(status: MessageStatus | str) -> str:
    emoji = get_status_emoji(status)
    label = STATUS_LABELS.get(status, "Помилка")

    return f"{emoji} {label}"


def get_request_status_keyboard(current_status: MessageStatus) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for status in MessageStatus:
        if status != current_status:
            kb.button(
                text=get_status_label(status),
                callback_data=MessageCallback(action="set_status", data=status.value),
            )

    kb.adjust(1)

    return kb.as_markup()
