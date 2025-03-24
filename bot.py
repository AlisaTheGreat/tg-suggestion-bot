import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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

AUTO_HASHTAGS = "#тф #team_fortress2"
BASE_SIGNATURE = "@TwoFortKitchen\n➡️ <a href='https://t.me/kitchen_2fort_bot'>Предложка</a>"

def format_username(user: types.User) -> str:
    name = user.full_name or "Безымянный"
    profile = f"<a href='tg://user?id={user.id}'>{name}</a>"
    return f"👤 {profile}"

def get_admin_keyboard(user_id: int, msg_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅", callback_data=f"approve:{msg_id}"),
            InlineKeyboardButton(text="🗑 Отклонить", callback_data=f"decline:{msg_id}:{user_id}")
        ],
        [
            InlineKeyboardButton(text="👤", url=f"tg://user?id={user_id}")
        ]
    ])

@dp.message(CommandStart())
async def start(message: types.Message):
    greeting = "Привет, админы! Я — предложка канала Кухни Туфорта. Бота сделала Алиса." if message.chat.id == ADMIN_CHAT_ID else (
        "Привет! Это предложка канала <b>Кухни Туфорта</b>.\n\nОтправь сюда текст или медиа — и оно попадёт к админам на рассмотрение.\nСпасибо за идею!"
    )
    await message.answer(greeting, parse_mode=ParseMode.HTML)

@dp.message()
async def handle_suggestion(message: types.Message):
    if message.chat.type != "private":
        return

    # Сохраняем оригинал до пересылки
    original = message
    text = original.text or original.caption or ""

    forwarded = await message.copy_to(ADMIN_CHAT_ID)
    user_tag = format_username(original.from_user)
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

    # 👤 Только имя Telegram-аккаунта (не username и не ссылка)
    name = user.full_name or ""
    author_line = f"👤 {name}" if name.strip() else ""

    # Финальный текст/подпись
    caption = f"{text.strip()}"
    if author_line:
        caption += f"\n\n{author_line}"
    caption += f"\n\n{AUTO_HASHTAGS}\n\n{BASE_SIGNATURE}"

    try:
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

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
