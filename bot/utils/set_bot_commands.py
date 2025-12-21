from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeChatAdministrators,
)


async def set_bot_commands_for_private_chats(bot: Bot) -> None:
    await bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="Запустити бота"),
            BotCommand(command="verify", description="Верифікувати старосту"),
            BotCommand(
                command="create_organization", description="Створити організацію"
            ),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    )


async def set_bot_commands_for_admin_chat(
    bot: Bot, admin_chat_id: int, is_root_organization: bool = False
) -> None:
    commands = [
        # Admin management commands
        BotCommand(command="settings", description="Налаштування організації"),
        BotCommand(
            command="rename_organization", description="Перейменувати організацію"
        ),
        BotCommand(command="set_admin_chat", description="Встановити адмін чат"),
        BotCommand(command="set_bot", description="Встановити бота"),
        BotCommand(command="delete_bot", description="Видалити бота"),
        BotCommand(
            command="set_greeting",
            description="Встановити вітальне повідомлення",
        ),
        BotCommand(
            command="delete_greeting",
            description="Видалити вітальне повідомлення",
        ),
        # Chat management
        BotCommand(command="delete_selected_chat", description="Видалити обраний чат"),
        # Ban management
        BotCommand(command="ban", description="Заблокувати користувача"),
        BotCommand(command="unban", description="Розблокувати користувача"),
        BotCommand(command="ban_list", description="Список заблокованих користувачів"),
        # Captain management
        BotCommand(
            command="set_captains_spreadsheet", description="Встановити таблицю старост"
        ),
        BotCommand(
            command="delete_captains_spreadsheet",
            description="Видалити таблицю старост",
        ),
        BotCommand(command="spam_groups", description="Розсилка до груп"),
        BotCommand(command="spam_captains", description="Розсилка до старост"),
        BotCommand(command="spam_all_groups", description="Розсилка до всіх груп"),
        BotCommand(command="spam_all_captains", description="Розсилка до всіх старост"),
        BotCommand(command="captains_list", description="Вивести список старост"),
        BotCommand(
            command="update_captains", description="Оновити дані з таблиці старост"
        ),
        # Request management
        BotCommand(command="send", description="Надіслати повідомлення"),
        BotCommand(command="send_task", description="Надіслати завдання"),
        BotCommand(command="pending", description="Незавершені запити"),
        BotCommand(command="pending_chat", description="Незавершені запити чату"),
    ]

    if is_root_organization:
        commands.extend(
            [
                BotCommand(command="organizations", description="Список організацій"),
                BotCommand(
                    command="delete_organization", description="Видалити організацію"
                ),
                BotCommand(
                    command="update_commands", description="Оновити список команд"
                ),
            ]
        )

    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeChat(chat_id=admin_chat_id),
    )


async def set_bot_commands_for_internal_chat(
    bot: Bot, chat_id: int, is_forum: bool = False
) -> None:
    user_commands = [
        # Chat info
        BotCommand(command="members", description="Учасники чату"),
        BotCommand(command="groups", description="Список груп"),
        BotCommand(command="group_members", description="Учасники груп"),
        BotCommand(command="chat", description="Інформація про чат"),
        # Request management
        BotCommand(command="send", description="Надіслати повідомлення"),
        BotCommand(command="send_task", description="Надіслати завдання"),
        BotCommand(command="pending", description="Незавершені запити"),
        BotCommand(command="pending_chat", description="Незавершені запити чату"),
    ]

    admin_commands = [
        # Admin commands
        BotCommand(command="rename_chat", description="Перейменувати чат"),
        BotCommand(command="chat_visibility", description="Видимість чату"),
        BotCommand(command="delete_chat", description="Видалити чат"),
        BotCommand(command="pin_chat_requests", description="Закріпити запити в чаті"),
        BotCommand(
            command="disable_pin_chat_requests", description="Не закріплювати запити"
        ),
        BotCommand(command="set_chat_tags", description="Встановити теги чату"),
        BotCommand(command="delete_chat_tags", description="Видалити теги чату"),
        # Spam groups and captains
        BotCommand(command="spam_groups", description="Розсилка до груп"),
        BotCommand(command="spam_captains", description="Розсилка до старост"),
        BotCommand(command="spam_all_groups", description="Розсилка до всіх груп"),
        BotCommand(command="spam_all_captains", description="Розсилка до всіх старост"),
        BotCommand(command="captains_list", description="Вивести список старост"),
        BotCommand(
            command="update_captains", description="Оновити дані з таблиці старост"
        ),
    ]

    if is_forum:
        user_commands.append(BotCommand(command="threads", description="Гілки чату"))
        admin_commands.extend(
            [
                BotCommand(command="set_thread", description="Додати гілку"),
                BotCommand(command="delete_thread", description="Видалити гілку"),
                BotCommand(command="rename_thread", description="Перейменувати гілку"),
                BotCommand(command="thread_visibility", description="Видимість гілки"),
                BotCommand(
                    command="pin_thread_requests",
                    description="Закріпити запити в гілці",
                ),
                BotCommand(
                    command="disable_pin_thread_requests",
                    description="Не закріплювати запити",
                ),
                BotCommand(
                    command="set_thread_tags", description="Встановити теги гілки"
                ),
                BotCommand(
                    command="delete_thread_tags", description="Видалити теги гілки"
                ),
            ]
        )

    admin_commands.extend(user_commands)

    await bot.set_my_commands(
        commands=user_commands,
        scope=BotCommandScopeChat(chat_id=chat_id),
    )
    await bot.set_my_commands(
        commands=admin_commands,
        scope=BotCommandScopeChatAdministrators(chat_id=chat_id),
    )


async def set_bot_commands_for_external_chat(bot: Bot, chat_id: int) -> None:
    commands = [
        BotCommand(command="start", description="Запустити бота"),
        BotCommand(command="verify", description="Верифікувати чат"),
        BotCommand(command="migrate", description="Мігрувати чат"),
        BotCommand(command="send", description="Надіслати повідомлення"),
    ]

    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeChat(chat_id=chat_id),
    )


async def remove_bot_commands(bot: Bot, chat_id: int) -> None:
    await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))
