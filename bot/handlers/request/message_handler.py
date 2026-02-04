import html
from typing import Any
from aiogram import Bot
from aiogram.types import Message, ReactionTypeEmoji, User, BufferedInputFile, MessageId
from aiogram.enums import ChatType as TelegramChatType
from sqlalchemy import and_, literal, or_, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import crypto
from app.core.logger import logger
from app.core.enums import CryptoInfo, MessageType, MessageStatus, ChatType
from app.db.models.banned_user import BannedUser
from app.db.models.chat import Chat
from app.db.models.chat_captain import ChatCaptain
from app.db.models.chat_user import ChatUser
from app.db.models.message import Message as MessageDB
from app.db.models.organization import Organization
from app.db.models.telegram_bot import TelegramBot
from bot.middlewares.db_session import LazyDbSession
from bot.utils.format_user import format_user_info_html
from bot.utils.is_no_status_request import is_no_status_request
from bot.utils.request_statuses import get_request_status_keyboard, get_status_label


async def resend_message(
    message: Message,
    bot: Bot,
    chat_id: int,
    thread_id: int | None = None,
    reply_to_message_id: int | None = None,
) -> Message:
    common: dict[str, Any] = dict(
        chat_id=chat_id,
        message_thread_id=thread_id,
        reply_to_message_id=reply_to_message_id,
        protect_content=message.has_protected_content,
        reply_markup=message.reply_markup,
        business_connection_id=message.business_connection_id,
        message_effect_id=message.effect_id,
    )

    if message.text:
        return await bot.send_message(
            text=message.text,
            entities=message.entities,
            link_preview_options=message.link_preview_options,
            **common,
        )

    if message.sticker:
        return await bot.send_sticker(
            sticker=message.sticker.file_id,
            **common,
        )

    if message.location:
        return await bot.send_location(
            latitude=message.location.latitude,
            longitude=message.location.longitude,
            horizontal_accuracy=message.location.horizontal_accuracy,
            live_period=message.location.live_period,
            heading=message.location.heading,
            proximity_alert_radius=message.location.proximity_alert_radius,
            **common,
        )

    if message.venue:
        return await bot.send_venue(
            latitude=message.venue.location.latitude,
            longitude=message.venue.location.longitude,
            title=message.venue.title,
            address=message.venue.address,
            foursquare_id=message.venue.foursquare_id,
            foursquare_type=message.venue.foursquare_type,
            google_place_id=message.venue.google_place_id,
            google_place_type=message.venue.google_place_type,
            **common,
        )

    if message.contact:
        return await bot.send_contact(
            phone_number=message.contact.phone_number,
            first_name=message.contact.first_name,
            last_name=message.contact.last_name,
            vcard=message.contact.vcard,
            **common,
        )

    if message.dice:
        return await bot.send_dice(
            emoji=message.dice.emoji,
            **common,
        )

    async def download_media(file: Any, filename: str) -> BufferedInputFile:
        if message.bot is None:
            raise ValueError("message.bot is None, cannot get file URL.")

        tg_file = await message.bot.get_file(file.file_id)
        if not tg_file.file_path:
            raise ValueError("File path is None, cannot download the file.")

        file_data = await message.bot.download_file(tg_file.file_path)
        if file_data is None:
            raise ValueError("File was not downloaded")

        file_bytes = file_data.read()

        return BufferedInputFile(file_bytes, filename=filename)

    if message.photo:
        photo = await download_media(message.photo[-1], filename="photo.jpg")
        return await bot.send_photo(
            photo=photo,
            caption=message.caption,
            caption_entities=message.caption_entities,
            has_spoiler=message.has_media_spoiler,
            show_caption_above_media=message.show_caption_above_media,
            **common,
        )

    if message.video:
        filename = getattr(message.video, "file_name", "video.mp4")
        video = await download_media(message.video, filename=filename)
        return await bot.send_video(
            video=video,
            duration=message.video.duration,
            width=message.video.width,
            height=message.video.height,
            caption=message.caption,
            caption_entities=message.caption_entities,
            has_spoiler=message.has_media_spoiler,
            show_caption_above_media=message.show_caption_above_media,
            start_timestamp=message.video.start_timestamp,
            **common,
        )

    if message.animation:
        filename = getattr(message.animation, "file_name", "animation.gif")
        animation = await download_media(message.animation, filename=filename)
        return await bot.send_animation(
            animation=animation,
            duration=message.animation.duration,
            width=message.animation.width,
            height=message.animation.height,
            caption=message.caption,
            caption_entities=message.caption_entities,
            has_spoiler=message.has_media_spoiler,
            show_caption_above_media=message.show_caption_above_media,
            **common,
        )

    if message.audio:
        filename = getattr(message.audio, "file_name", "audio.mp3")
        audio = await download_media(message.audio, filename=filename)
        return await bot.send_audio(
            audio=audio,
            caption=message.caption,
            caption_entities=message.caption_entities,
            duration=message.audio.duration,
            performer=message.audio.performer,
            title=message.audio.title,
            **common,
        )

    if message.voice:
        voice = await download_media(message.voice, filename="voice.ogg")
        return await bot.send_voice(
            voice=voice,
            caption=message.caption,
            caption_entities=message.caption_entities,
            duration=message.voice.duration,
            **common,
        )

    if message.document:
        filename = getattr(message.document, "file_name", "document")
        document = await download_media(message.document, filename=filename)
        return await bot.send_document(
            document=document,
            caption=message.caption,
            caption_entities=message.caption_entities,
            **common,
        )

    if message.video_note:
        video_note = await download_media(message.video_note, filename="video_note.mp4")
        return await bot.send_video_note(
            video_note=video_note,
            duration=message.video_note.duration,
            length=message.video_note.length,
            **common,
        )

    raise Exception(f"Unsupported message type: {message.content_type}")


async def copy_message(
    message: Message,
    to_send_chat_id: int,
    to_send_thread_id: int | None,
    reply_to_message_id: int | None,
    bot: Bot | None = None,
) -> int:
    if not message.from_user or not message.bot:
        raise Exception("Can not copy message: from_user or bot not provided")

    if bot is None:
        is_same_bot = True
        bot = message.bot
    else:
        is_same_bot = bot.id == message.bot.id

    forwarded_msg: Message | MessageId | None = None

    if is_same_bot:
        try:
            forwarded_msg = await message.copy_to(
                chat_id=to_send_chat_id,
                message_thread_id=to_send_thread_id,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception as e:
            if "message thread not found" in str(e):
                forwarded_msg = await message.copy_to(
                    chat_id=to_send_chat_id,
                    reply_to_message_id=reply_to_message_id,
                )
            elif "message to be replied not found" in str(e):
                forwarded_msg = await message.copy_to(
                    chat_id=to_send_chat_id,
                    message_thread_id=to_send_thread_id,
                )
            else:
                raise
    else:
        try:
            forwarded_msg = await resend_message(
                message, bot, to_send_chat_id, to_send_thread_id, reply_to_message_id
            )
        except Exception as e:
            if "message thread not found" in str(e):
                forwarded_msg = await resend_message(
                    message,
                    bot,
                    to_send_chat_id,
                    None,
                    reply_to_message_id,
                )
            elif "message to be replied not found" in str(e):
                forwarded_msg = await resend_message(
                    message,
                    bot,
                    to_send_chat_id,
                    to_send_thread_id,
                )
            else:
                raise

    return forwarded_msg.message_id


async def send_message(
    db: AsyncSession,
    message: Message,
    to_send_chat_id: int,
    to_send_thread_id: int | None,
    reply_to_message_id: int | None,
    message_type: MessageType,
    additional_service_text: str | None = None,
    feedback_send_destination: str | None = None,
    user: User | None = None,
    bot: Bot | None = None,
    is_no_status_request: bool = False,
) -> int | None:
    if not message.from_user or not message.bot or message_type == MessageType.SERVICE:
        return None

    if user is None:
        user = message.from_user

    if bot is None:
        bot = message.bot
        is_within_organization = True
    else:
        is_within_organization = message.bot.id == bot.id

    corrected_thread_id = (
        message.message_thread_id
        if message.chat.is_forum
        and (
            not message.reply_to_message
            or (
                not message.reply_to_message.forum_topic_created
                and message.reply_to_message.message_id != message.message_thread_id
            )
        )
        else None
    )
    corrected_to_send_thread_id = to_send_thread_id if to_send_thread_id != 1 else None

    if message_type in (MessageType.REQUEST, MessageType.TASK):
        if message_type == MessageType.REQUEST:
            service_text = f"#R{user.id}, {format_user_info_html(user, False)}"
        else:
            service_text = f"📝 {format_user_info_html(user)}"

        if additional_service_text:
            service_text += f"\n{additional_service_text}"

        if is_no_status_request:
            status = None
            keyboard = None
            is_status_reference = None
        else:
            status = MessageStatus.NEW
            label = get_status_label(MessageStatus.NEW)
            service_text += f"\n\n{label}"
            keyboard = get_request_status_keyboard(MessageStatus.NEW)
            is_status_reference = False

        try:
            service_msg = await bot.send_message(
                to_send_chat_id,
                service_text,
                message_thread_id=corrected_to_send_thread_id,
                reply_markup=keyboard,
                reply_to_message_id=reply_to_message_id,
                parse_mode="HTML",
            )
        except Exception as e:
            if "message thread not found" in str(e):
                service_msg = await bot.send_message(
                    to_send_chat_id,
                    service_text,
                    reply_markup=keyboard,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode="HTML",
                )
                corrected_to_send_thread_id = None
                to_send_thread_id = None
            elif "message to be replied not found" in str(e):
                service_msg = await bot.send_message(
                    to_send_chat_id,
                    service_text,
                    message_thread_id=corrected_to_send_thread_id,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                reply_to_message_id = None
            else:
                raise

        db.add(
            MessageDB(
                user_id=user.id,
                chat_id=message.chat.id,
                thread_id=corrected_thread_id,
                message_id=message.message_id,
                destination_chat_id=to_send_chat_id,
                destination_thread_id=to_send_thread_id,
                destination_message_id=service_msg.message_id,
                is_within_organization=is_within_organization,
                type=MessageType.SERVICE,
                status=status,
                is_status_reference=is_status_reference,
                text=service_text,
            )
        )

        if message_type == MessageType.TASK:
            if is_no_status_request:
                text = "Завдання надіслано"
            else:
                text = f"{label}\nЗавдання надіслано"

            if feedback_send_destination:
                text += f" {feedback_send_destination}"

            feedback_message = await message.answer(
                text,
                parse_mode="HTML",
                reply_to_message_id=message.message_id,
            )

            if not is_no_status_request:
                db.add(
                    MessageDB(
                        user_id=user.id,
                        chat_id=to_send_chat_id,
                        thread_id=to_send_thread_id,
                        message_id=service_msg.message_id,
                        destination_chat_id=message.chat.id,
                        destination_thread_id=corrected_thread_id,
                        destination_message_id=feedback_message.message_id,
                        is_within_organization=is_within_organization,
                        type=MessageType.SERVICE,
                        status=MessageStatus.NEW,
                        is_status_reference=True,
                        text=text,
                    )
                )
        elif feedback_send_destination:
            await message.answer(
                f"Надіслано {feedback_send_destination}", parse_mode="HTML"
            )

    elif message_type in (MessageType.INFO, MessageType.SPAM):
        if message_type == MessageType.SPAM:
            service_text = "ℹ️ Розсилка"
            if additional_service_text:
                service_text += f" {additional_service_text}"
        else:
            service_text = f"ℹ️ Повідомлення від {format_user_info_html(user)}"
            if additional_service_text:
                service_text += f"\n{additional_service_text}"

        try:
            service_msg = await bot.send_message(
                to_send_chat_id,
                service_text,
                message_thread_id=corrected_to_send_thread_id,
                reply_to_message_id=reply_to_message_id,
                parse_mode="HTML",
            )
        except Exception as e:
            if "message thread not found" in str(e):
                service_msg = await bot.send_message(
                    to_send_chat_id,
                    service_text,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode="HTML",
                )
                corrected_to_send_thread_id = None
                to_send_thread_id = None
            elif "message to be replied not found" in str(e):
                service_msg = await bot.send_message(
                    to_send_chat_id,
                    service_text,
                    message_thread_id=corrected_to_send_thread_id,
                    parse_mode="HTML",
                )
                reply_to_message_id = None
            else:
                raise

        db.add(
            MessageDB(
                user_id=user.id,
                chat_id=message.chat.id,
                thread_id=corrected_thread_id,
                message_id=message.message_id,
                destination_chat_id=to_send_chat_id,
                destination_thread_id=to_send_thread_id,
                destination_message_id=service_msg.message_id,
                is_within_organization=is_within_organization,
                type=MessageType.SERVICE,
                text=service_text,
            )
        )

        if feedback_send_destination:
            await message.answer(
                f"Надіслано {feedback_send_destination}",
                parse_mode="HTML",
                reply_to_message_id=message.message_id,
            )
    elif message_type == MessageType.INFO_REPLY:
        find_chat_stmt = (
            select(Chat)
            .options(joinedload(Chat.organization))
            .where(Chat.id.in_((message.chat.id, to_send_chat_id)))
        )
        chats_result = await db.execute(find_chat_stmt)
        chats = chats_result.scalars().all()

        origin: Chat | Organization | None = None
        destination: Chat | Organization | None = None

        if chats:
            if len(chats) == 1:
                one_chat = chats[0]
                if one_chat.id == message.chat.id:
                    origin = one_chat
                else:
                    destination = one_chat
            else:
                origin, destination = chats
                if destination.id == message.chat.id:
                    origin, destination = destination, origin

        if destination is None:
            if origin is None:
                find_orgs_stmt = select(Organization).where(
                    Organization.admin_chat_id.in_((message.chat.id, to_send_chat_id))
                )
                organizations_res = await db.execute(find_orgs_stmt)
                organizations = organizations_res.scalars().all()

                if len(organizations) == 1:
                    one_org = organizations[0]
                    if one_org.admin_chat_id == message.chat.id:
                        origin = one_org
                    else:
                        destination = one_org
                elif len(organizations) == 2:
                    origin, destination = organizations
                    if destination.admin_chat_id == message.chat.id:
                        origin, destination = destination, origin

            else:
                find_org_dest_stmt = select(Organization).where(
                    Organization.admin_chat_id == to_send_chat_id
                )
                org_dest_res = await db.execute(find_org_dest_stmt)
                destination = org_dest_res.scalar_one_or_none()
        elif origin is None:
            find_org_origin_stmt = select(Organization).where(
                Organization.admin_chat_id == message.chat.id
            )
            find_org_origin_res = await db.execute(find_org_origin_stmt)
            origin = find_org_origin_res.scalar_one_or_none()

        if destination and (
            isinstance(destination, Organization)
            or destination.type != ChatType.EXTERNAL
        ):
            service_text = f"ℹ️ Реплай від {format_user_info_html(user)}"

            if origin:
                service_text += "\n"

                if isinstance(origin, Organization):
                    service_text += f"Адміністратори {html.escape(origin.title)}"
                else:
                    if not is_within_organization:
                        service_text += f"{html.escape(origin.organization.title)}, "

                    if origin.type == ChatType.EXTERNAL:
                        service_text += "Чат групи "

                    service_text += html.escape(origin.title)

            try:
                service_msg = await bot.send_message(
                    to_send_chat_id,
                    service_text,
                    message_thread_id=corrected_to_send_thread_id,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode="HTML",
                )
            except Exception as e:
                if "message thread not found" in str(e):
                    service_msg = await bot.send_message(
                        to_send_chat_id,
                        service_text,
                        reply_to_message_id=reply_to_message_id,
                        parse_mode="HTML",
                    )
                    corrected_to_send_thread_id = None
                    to_send_thread_id = None
                elif "message to be replied not found" in str(e):
                    service_msg = await bot.send_message(
                        to_send_chat_id,
                        service_text,
                        message_thread_id=corrected_to_send_thread_id,
                        parse_mode="HTML",
                    )
                    reply_to_message_id = None
                else:
                    raise

    sent_msg_id = await copy_message(
        message,
        to_send_chat_id,
        corrected_to_send_thread_id,
        reply_to_message_id=(
            reply_to_message_id if message_type == MessageType.INFO_REPLY else None
        ),
        bot=bot,
    )

    db.add(
        MessageDB(
            user_id=user.id,
            chat_id=message.chat.id,
            thread_id=corrected_thread_id,
            message_id=message.message_id,
            destination_chat_id=to_send_chat_id,
            destination_thread_id=to_send_thread_id,
            destination_message_id=sent_msg_id,
            is_within_organization=is_within_organization,
            type=message_type,
            text=message.text or message.caption,
        )
    )

    await db.commit()

    return sent_msg_id


async def get_captain_or_chat_info(db: AsyncSession, user_id: int) -> str | None:
    captain_query = select(
        literal(1).label("p"),
        ChatCaptain.chat_title.label("r"),
    ).where(ChatCaptain.connected_user_id == user_id)

    external_chat_query = (
        select(
            literal(2).label("p"),
            Chat.title.label("r"),
        )
        .join(ChatUser, ChatUser.chat_id == Chat.id)
        .where(
            ChatUser.user_id == user_id,
            Chat.type == ChatType.EXTERNAL,
        )
    )

    union_q = captain_query.union_all(external_chat_query).subquery()
    stmt = select(union_q.c.p, union_q.c.r).order_by(union_q.c.p).limit(1)
    result_db = await db.execute(stmt)
    result: tuple[int, str] | None = result_db.tuples().one_or_none()

    if result is None:
        return None

    priority, value = result
    if priority == 1:
        return f"Староста {html.escape(value)}"

    return f"Студент {html.escape(value)}"


async def put_reaction(message: Message) -> None:
    try:
        await message.react([ReactionTypeEmoji(emoji="❤")])
    except Exception as e:
        logger.error(e)
        await message.reply("Повідомлення надіслано, сердечко поставити не вдалось.")


async def process_reply_request(
    db: AsyncSession, message: Message, organization: Organization
) -> bool:
    if not message.from_user or not message.bot or not message.reply_to_message:
        return False

    stmt = (
        select(MessageDB)
        .where(
            or_(
                and_(
                    MessageDB.destination_chat_id == message.chat.id,
                    MessageDB.destination_message_id
                    == message.reply_to_message.message_id,
                ),
                and_(
                    MessageDB.chat_id == message.chat.id,
                    MessageDB.message_id == message.reply_to_message.message_id,
                    MessageDB.user_id == message.from_user.id,
                    MessageDB.type != MessageType.SPAM,
                ),
            ),
            MessageDB.type != MessageType.SERVICE,
        )
        .order_by(MessageDB.id)
        .limit(1)
    )

    result = await db.execute(stmt)
    request_msg = result.scalar_one_or_none()

    if request_msg is None:
        return False

    to_send_chat_id: int | None = None
    to_send_thread_id: int | None = None
    reply_to_msg_id: int | None = None
    message_type = (
        MessageType.REQUEST
        if message.chat.type == TelegramChatType.PRIVATE
        else MessageType.INFO_REPLY
    )

    if request_msg.is_within_organization:
        bot = message.bot
    else:
        where_chat = (
            request_msg.destination_chat_id
            if request_msg.chat_id == message.chat.id
            else request_msg.chat_id
        )
        banned_exists = (
            select(1)
            .select_from(BannedUser)
            .where(
                BannedUser.organization_id == Organization.id,
                BannedUser.user_id == message.from_user.id,
            )
            .exists()
        )
        query = (
            select(
                TelegramBot.id,
                TelegramBot.token,
                banned_exists.label("is_banned"),
            )
            .join(Organization)
            .outerjoin(Chat)
            .where(or_(Chat.id == where_chat, Organization.admin_chat_id == where_chat))
            .limit(1)
        )
        bot_result_db = await db.execute(query)
        bot_result = bot_result_db.tuples().one_or_none()

        if bot_result is None:
            await message.reply(
                "❌ Не вдалось знайти бота або чат через якого було надіслано повідомлення"
            )
            return True

        bot_id, bot_token_encrypted, is_banned = bot_result
        if is_banned:
            await message.reply("❌ Вас було заблоковано")
            return True

        token_stripped = crypto.decrypt_data(bot_token_encrypted, CryptoInfo.BOT_TOKEN)
        token = f"{bot_id}:{token_stripped}"
        bot = Bot(token)

    service_message: MessageDB | None = None

    if request_msg.chat_id == message.chat.id:
        to_send_chat_id = request_msg.destination_chat_id
        to_send_thread_id = request_msg.destination_thread_id
        reply_to_msg_id = request_msg.destination_message_id
    else:
        to_send_chat_id = request_msg.chat_id
        to_send_thread_id = request_msg.thread_id
        reply_to_msg_id = request_msg.message_id

        if request_msg.type in (MessageType.REQUEST, MessageType.TASK):
            service_stmt = (
                select(MessageDB)
                .where(
                    MessageDB.chat_id == request_msg.chat_id,
                    MessageDB.message_id == request_msg.message_id,
                    MessageDB.type == MessageType.SERVICE,
                    or_(
                        MessageDB.status != MessageStatus.COMPLETED,
                        MessageDB.status.is_(None),
                    ),
                    MessageDB.text.is_not(None),
                )
                .limit(1)
            )
            service_result = await db.execute(service_stmt)
            service_message = service_result.scalar_one_or_none()
            if service_message and service_message.text:
                if service_message.status is None:
                    service_previous_stmt = (
                        select(MessageDB)
                        .where(
                            MessageDB.chat_id == request_msg.chat_id,
                            MessageDB.destination_chat_id
                            == service_message.destination_chat_id,
                            MessageDB.type == MessageType.SERVICE,
                            MessageDB.status.is_not(None),
                            MessageDB.text.is_not(None),
                        )
                        .order_by(MessageDB.created_at.desc())
                        .limit(1)
                    )
                    service_previous_result = await db.execute(service_previous_stmt)
                    service_message = service_previous_result.scalar_one_or_none()

                if (
                    service_message
                    and service_message.status is not None
                    and service_message.status != MessageStatus.COMPLETED
                    and service_message.text
                ):
                    service_message.status = MessageStatus.COMPLETED
                    service_message.status_changed_by_user = message.from_user.id

                    new_label = get_status_label(MessageStatus.COMPLETED)
                    old_service_text = service_message.text.rsplit("\n", 1)[0]
                    user_info = (
                        f"@{message.from_user.username}"
                        if message.from_user.username
                        else message.from_user.full_name
                    )
                    updated_text = f"{old_service_text}\n{new_label} [{user_info}]"
                    service_message.text = updated_text

                    service_msg_ref_stmt = select(MessageDB).where(
                        MessageDB.chat_id == service_message.destination_chat_id,
                        MessageDB.message_id == service_message.destination_message_id,
                        MessageDB.type == MessageType.SERVICE,
                        MessageDB.status.is_not(None),
                        MessageDB.is_status_reference.is_(True),
                    )
                    service_msg_ref_res = await db.execute(service_msg_ref_stmt)
                    service_msg_reference = service_msg_ref_res.scalar_one_or_none()

                    if service_msg_reference:
                        if service_msg_reference.text:
                            service_text = service_msg_reference.text.split("\n", 1)[1]
                            updated_reference_text = f"{new_label}\n{service_text}"

                            try:
                                await bot.edit_message_text(
                                    text=updated_reference_text,
                                    chat_id=service_msg_reference.destination_chat_id,
                                    message_id=service_msg_reference.destination_message_id,
                                )
                            except Exception:
                                try:
                                    await bot.send_message(
                                        service_msg_reference.destination_chat_id,
                                        f"Не вдалось змінити повідомлення. Статус змінено на: {new_label}",
                                        message_thread_id=service_msg_reference.destination_thread_id,
                                        reply_to_message_id=service_msg_reference.destination_message_id,
                                    )
                                except Exception as e:
                                    logger.error(e)

                            service_msg_reference.text = updated_reference_text

                        service_msg_reference.status = MessageStatus.COMPLETED
                        service_msg_reference.status_changed_by_user = (
                            message.from_user.id
                        )

    additional_info: str | None = None
    if message.chat.type == TelegramChatType.PRIVATE:
        additional_info = await get_captain_or_chat_info(db, message.from_user.id)

    try:
        try:
            await send_message(
                db,
                message,
                to_send_chat_id,
                to_send_thread_id,
                reply_to_msg_id,
                message_type,
                additional_info,
                bot=bot,
            )
            await put_reaction(message)
        except Exception as e:
            if "bot was blocked by the user" in str(e):
                await message.answer(
                    "Користувач заблокував бота, відповідь не була надіслана"
                )
            else:
                raise

        if service_message and service_message.text:
            to_use_bot = bot if request_msg.chat_id == message.chat.id else message.bot

            try:
                await to_use_bot.edit_message_text(
                    service_message.text,
                    chat_id=service_message.destination_chat_id,
                    message_id=service_message.destination_message_id,
                    reply_markup=get_request_status_keyboard(MessageStatus.COMPLETED),
                    parse_mode="HTML",
                )
            except Exception as e:
                error_text = str(e)
                ignored_errors = (
                    "bot was blocked by the user",
                    "TOPIC_CLOSED",
                )
                if not any(err in error_text for err in ignored_errors):
                    await to_use_bot.send_message(
                        service_message.destination_chat_id,
                        f"Не вдалось змінити повідомлення. Статус змінено на: {new_label} [{user_info}]",
                        message_thread_id=service_message.destination_thread_id,
                        reply_to_message_id=service_message.destination_message_id,
                    )
    finally:
        if not request_msg.is_within_organization:
            await bot.session.close()

    return True


async def send_admin_request(
    db: AsyncSession, message: Message, organization: Organization
) -> None:
    if not message.from_user or not message.bot or not organization.admin_chat_id:
        return

    additional_info = await get_captain_or_chat_info(db, message.from_user.id)
    is_no_status = await is_no_status_request(db, message, organization.admin_chat_id)

    await send_message(
        db,
        message,
        organization.admin_chat_id,
        organization.admin_chat_thread_id,
        None,
        MessageType.REQUEST,
        additional_info,
        is_no_status_request=is_no_status,
    )
    await put_reaction(message)


async def message_handler(
    message: Message,
    lazy_db: LazyDbSession,
    organization: Organization,
) -> None:
    if not message.from_user or not message.bot:
        return

    if message.reply_to_message:
        db = await lazy_db.get()
        if await process_reply_request(db, message, organization):
            return

    if message.chat.type == TelegramChatType.PRIVATE:
        if not organization.is_admins_accept_messages or not organization.admin_chat_id:
            await message.answer("❌ Адміністратори не приймають повідомлення.")
            return

        db = await lazy_db.get()
        await send_admin_request(db, message, organization)
        return
