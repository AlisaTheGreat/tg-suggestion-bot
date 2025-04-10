import os
import asyncio
import time
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAnimation,
)
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from aiogram.client.default import DefaultBotProperties

load_dotenv()

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

user_message_map = {}
text_buffer = {}
media_buffer = {}
group_buffer = defaultdict(list)
group_timestamps = {}
group_collect_tasks = {}

AUTO_HASHTAGS = "#тф #team_fortress2"
BASE_SIGNATURE = "@TwoFortKitchen\n➡️ <a href='https://t.me/kitchen_2fort_bot'>Предложка</a>"

def get_admin_keyboard(user_id: int, msg_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅", callback_data=f"approve:{msg_id}"),
            InlineKeyboardButton(text="🗑 Отклонить", callback_data=f"decline:{msg_id}:{user_id}")
        ],
        [
            InlineKeyboardButton(text="🚫 BAN", callback_data=f"ban:{user_id}"),
            InlineKeyboardButton(text="👤", url=f"tg://user?id={user_id}")
        ]
    ])

@dp.message(CommandStart())
async def start(message: types.Message):
    greeting = "Привет, админы! Я — предложка канала Кухни Туфорта. Бота сделала Алиса." if message.chat.id == ADMIN_CHAT_ID else (
        "Привет! Это предложка канала <b>Кухни Туфорта</b>.\n\nОтправь сюда текст или медиа — и оно попадёт к админам на рассмотрение.\nСпасибо за идею!"
    )
    await message.answer(greeting)

@dp.message(F.media_group_id)
async def handle_album(message: types.Message):
    group_id = message.media_group_id
    group_buffer[group_id].append(message)
    group_timestamps[group_id] = time.time()

    if group_id in group_collect_tasks:
        return

    async def collect_album():
        await asyncio.sleep(1.2)
        messages = group_buffer.pop(group_id, [])
        group_timestamps.pop(group_id, None)
        group_collect_tasks.pop(group_id, None)

        if not messages:
            return

        user = messages[0].from_user
        caption = messages[0].caption or ""
        media = []

        for i, msg in enumerate(messages):
            cap = caption if i == 0 else None
            if msg.photo:
                media.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=cap))
            elif msg.video:
                media.append(InputMediaVideo(media=msg.video.file_id, caption=cap))
            elif msg.animation:
                media.append(InputMediaAnimation(media=msg.animation.file_id, caption=cap))

        # Отправляем весь альбом админам
        preview_group = await bot.send_media_group(ADMIN_CHAT_ID, media=media)

        # Кнопки к отдельному сообщению (реплаем на первую фотку)
        info_message = await bot.send_message(
            ADMIN_CHAT_ID,
            f"👤 {user.full_name}",
            reply_to_message_id=preview_group[0].message_id,
            reply_markup=get_admin_keyboard(user.id, preview_group[0].message_id)
        )

        # Привязка к первому сообщению альбома
        user_message_map[preview_group[0].message_id] = user.id
        text_buffer[preview_group[0].message_id] = caption
        media_buffer[preview_group[0].message_id] = media

        await messages[0].answer("Спасибо! Ваше сообщение отправлено на рассмотрение админам.")

    group_collect_tasks[group_id] = asyncio.create_task(collect_album())

@dp.message()
async def handle_single_message(message: types.Message):
    if message.chat.type != "private":
        return

    original = message
    text = original.text or original.caption or ""

    forwarded = await message.copy_to(ADMIN_CHAT_ID)
    user_tag = f"👤 {original.from_user.full_name}" if original.from_user.full_name else ""

    kb = get_admin_keyboard(original.from_user.id, forwarded.message_id)
    user_message_map[forwarded.message_id] = original.from_user.id
    text_buffer[forwarded.message_id] = text
    media_buffer[forwarded.message_id] = original

    await bot.send_message(
        ADMIN_CHAT_ID,
        user_tag,
        reply_to_message_id=forwarded.message_id,
        reply_markup=kb
    )
    await message.reply("Спасибо! Ваше сообщение отправлено на рассмотрение админам.")

@dp.callback_query(lambda c: c.data.startswith("approve:"))
async def approve_post(callback: types.CallbackQuery):
    msg_id = int(callback.data.split(":")[1])
    user_id = user_message_map.get(msg_id)
    text = text_buffer.get(msg_id)
    original = media_buffer.get(msg_id)

    if not user_id or not original:
        await callback.answer("Невозможно опубликовать: отсутствует текст или автор.", show_alert=True)
        return

    user = await bot.get_chat(user_id)
    name = user.full_name or ""
    author_line = f"👤 {name}" if name.strip() else ""

    caption = text.strip()
    if author_line:
        caption += f"\n\n{author_line}"
    caption += f"\n\n{AUTO_HASHTAGS}\n\n{BASE_SIGNATURE}"

    try:
        if isinstance(original, list):
            original[0].caption = caption
            await bot.send_media_group(CHANNEL_ID, media=original)
        elif isinstance(original, types.Message):
            if original.photo:
                await bot.send_photo(CHANNEL_ID, original.photo[-1].file_id, caption=caption)
            elif original.video:
                await bot.send_video(CHANNEL_ID, original.video.file_id, caption=caption)
            elif original.animation:
                await bot.send_animation(CHANNEL_ID, original.animation.file_id, caption=caption)
            else:
                await bot.send_message(CHANNEL_ID, caption)
    except Exception as e:
        await callback.message.reply(f"❌ Ошибка при публикации: {e}")
        return

    await callback.message.edit_text("✅ Опубликовано.")
    await callback.answer("Отправлено в канал.")
    await bot.send_message(user_id, "Ваша предложка опубликована в канале Кухни Туфорта. Спасибо!")

@dp.callback_query(lambda c: c.data.startswith("decline:"))
async def decline_simple(callback: types.CallbackQuery):
    msg_id, user_id = map(int, callback.data.split(":")[1:])
    await callback.message.edit_text("❌ Отклонено.")
    await callback.answer("Пост отклонён.")
    await bot.send_message(user_id, "К сожалению, предложка не подошла, но спасибо за идею 💛")

@dp.callback_query(lambda c: c.data.startswith("ban:"))
async def ban_user(callback: types.CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    try:
        await bot.ban_chat_member(ADMIN_CHAT_ID, user_id)
        await callback.answer("Пользователь забанен.")
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
