def format_message_url(chat_id: int, thread_id: int | None, message_id: int) -> str:
    chat_id_str = str(chat_id)
    chat_id_str = chat_id_str.removeprefix("-100")

    if thread_id:
        return f"https://t.me/c/{chat_id_str}/{thread_id}/{message_id}"

    return f"https://t.me/c/{chat_id_str}/{message_id}"
