import asyncio
import html
import os
import sqlite3

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from keep_alive import keep_alive

keep_alive()

# === SOZLAMALAR ===
# Tokenni Render -> Environment bo'limiga BOT_TOKEN nomi bilan qo'ying
BOT_TOKEN = os.environ "8957925087:AAEk58gvdqNIJTYLPuMYg3_TUW9BkBU7qO4"
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6119649341"))
DB_PATH = os.environ.get("DB_PATH", "movies.db")
# ==================

# Hamma xabarlarda HTML ishlaydi (**...** va `...` endi ko'rinib qolmaydi)
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())


# === BAZA ===
def db():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            content_type TEXT,
            file_id TEXT,
            caption TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS channels (
            chat_id TEXT PRIMARY KEY,
            link TEXT,
            name TEXT
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def add_movie_db(code, content_type, file_id, caption):
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO movies (code, content_type, file_id, caption)"
        " VALUES (?, ?, ?, ?)",
        (code, content_type, file_id, caption),
    )
    conn.commit()
    conn.close()


def get_movie_db(code):
    conn = db()
    row = conn.execute(
        "SELECT content_type, file_id, caption FROM movies WHERE code = ?",
        (code,),
    ).fetchone()
    conn.close()
    if row:
        return {"type": row[0], "file_id": row[1], "caption": row[2]}
    return None


def delete_movie_db(code):
    conn = db()
    cur = conn.execute("DELETE FROM movies WHERE code = ?", (code,))
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count > 0


def get_channels_db():
    conn = db()
    rows = conn.execute("SELECT chat_id, link, name FROM channels").fetchall()
    conn.close()
    return [{"chat_id": r[0], "link": r[1], "name": r[2]} for r in rows]


def add_channel_db(chat_id, link, name):
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO channels (chat_id, link, name) VALUES (?, ?, ?)",
        (chat_id, link, name),
    )
    conn.commit()
    conn.close()


def delete_channel_db(chat_id):
    conn = db()
    conn.execute("DELETE FROM channels WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()


# === FSM HOLATLARI ===
class AddMovie(StatesGroup):
    waiting_for_code = State()
    waiting_for_type = State()
    waiting_for_content = State()


class DeleteMovie(StatesGroup):
    waiting_for_code = State()


class AddChannel(StatesGroup):
    waiting_for_id = State()
    waiting_for_link = State()
    waiting_for_name = State()


class DeleteChannel(StatesGroup):
    waiting_for_id = State()


# === TUGMALAR ===
def get_main_keyboard(is_admin: bool):
    buttons = [[KeyboardButton(text="🎬 Kino kodi yuborish")]]
    if is_admin:
        buttons.append(
            [
                KeyboardButton(text="➕ Yangi kino qo'shish"),
                KeyboardButton(text="🗑 Kinoni o'chirish"),
            ]
        )
        buttons.append([KeyboardButton(text="📢 Kanallarni boshqarish")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_type_keyboard():
    buttons = [
        [
            KeyboardButton(text="📹 Video"),
            KeyboardButton(text="🖼 Rasm"),
            KeyboardButton(text="📝 Matn"),
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons, resize_keyboard=True, one_time_keyboard=True
    )


# === A'ZOLIK TEKSHIRUVI ===
async def check_sub_channels(user_id: int):
    if user_id == ADMIN_ID:
        return []
    unsubscribed = []
    for ch in get_channels_db():
        try:
            member = await bot.get_chat_member(
                chat_id=ch["chat_id"], user_id=user_id
            )
            if member.status in (
                ChatMemberStatus.LEFT,
                ChatMemberStatus.KICKED,
            ):
                unsubscribed.append(ch)
        except Exception:
            unsubscribed.append(ch)
    return unsubscribed


def get_sub_keyboard(unsubscribed_channels, code: str = ""):
    kb = []
    for ch in unsubscribed_channels:
        kb.append(
            [InlineKeyboardButton(text=f"➕ {ch['name']}", url=ch["link"])]
        )
    cb_data = f"check_sub:{code}" if code else "check_sub_general"
    kb.append(
        [
            InlineKeyboardButton(
                text="✅ A'zolikni tekshirish", callback_data=cb_data
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


# === KINO YUBORISH ===
async def send_movie_to_user(chat_id: int, movie_data: dict):
    m_type = movie_data["type"]
    file_id = movie_data["file_id"]
    caption = movie_data["caption"]

    # parse_mode=None: admin yozgan matnda < > belgilari xatolik bermasin
    if m_type == "video":
        await bot.send_video(
            chat_id=chat_id, video=file_id, caption=caption, parse_mode=None
        )
    elif m_type == "photo":
        await bot.send_photo(
            chat_id=chat_id, photo=file_id, caption=caption, parse_mode=None
        )
    elif m_type == "text":
        await bot.send_message(chat_id=chat_id, text=caption, parse_mode=None)


# === START ===
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id == ADMIN_ID
    unsub = await check_sub_channels(message.from_user.id)

    if unsub:
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:",
            reply_markup=get_sub_keyboard(unsub),
        )
    else:
        name = html.escape(message.from_user.full_name)
        await message.answer(
            f"Assalomu alaykum, <b>{name}</b>!\n\n"
            "🎬 Kino qidirish uchun kodini yuboring yoki quyidagi tugmalardan"
            " foydalaning:",
            reply_markup=get_main_keyboard(is_admin),
        )


@dp.callback_query(F.data.startswith("check_sub"))
async def check_subscription_callback(callback: types.CallbackQuery):
    unsub = await check_sub_channels(callback.from_user.id)
    if unsub:
        await callback.answer(
            "❌ Barcha kanallarga a'zo bo'lmadingiz!", show_alert=True
        )
        return

    await callback.answer("✅ A'zolik tasdiqlandi!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

    parts = callback.data.split(":")
    if len(parts) > 1 and parts[1]:
        movie = get_movie_db(parts[1])
        if movie:
            await send_movie_to_user(callback.from_user.id, movie)
    else:
        await bot.send_message(
            callback.from_user.id,
            "✅ Endi kino kodini yuborishingiz mumkin.",
            reply_markup=get_main_keyboard(callback.from_user.id == ADMIN_ID),
        )


@dp.message(F.text == "🎬 Kino kodi yuborish")
async def ask_code_btn(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("⌨️ Kino kodini yuboring (masalan: <code>100</code>):")


# === ADMIN: KINO QO'SHISH ===
@dp.message(F.text == "➕ Yangi kino qo'shish", F.from_user.id == ADMIN_ID)
async def add_movie_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✏️ Yangi kino uchun <b>sonli kod</b> kiriting (masalan:"
        " <code>100</code>):",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(AddMovie.waiting_for_code)


@dp.message(AddMovie.waiting_for_code)
async def process_add_code(message: types.Message, state: FSMContext):
    code = (message.text or "").strip()
    if not code.isdigit():
        await message.answer("⚠️ Iltimos, kodni faqat raqamlarda kiriting!")
        return

    await state.update_data(code=code)
    await message.answer(
        "📂 Kino turini tanlang:", reply_markup=get_type_keyboard()
    )
    await state.set_state(AddMovie.waiting_for_type)


@dp.message(
    AddMovie.waiting_for_type, F.text.in_(["📹 Video", "🖼 Rasm", "📝 Matn"])
)
async def process_add_type(message: types.Message, state: FSMContext):
    selected = message.text
    if selected == "📹 Video":
        m_type = "video"
        msg = (
            "📹 Video faylni yuboring (izohiga kino haqida ma'lumot"
            " yozishingiz mumkin):"
        )
    elif selected == "🖼 Rasm":
        m_type = "photo"
        msg = (
            "🖼 Rasmni yuboring (izohiga kino haqida ma'lumot yozishingiz"
            " mumkin):"
        )
    else:
        m_type = "text"
        msg = "📝 Kino haqidagi matnni yuboring:"

    await state.update_data(m_type=m_type)
    await message.answer(msg, reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddMovie.waiting_for_content)


@dp.message(AddMovie.waiting_for_type)
async def wrong_type(message: types.Message):
    await message.answer(
        "⚠️ Pastdagi tugmalardan birini tanlang.",
        reply_markup=get_type_keyboard(),
    )


@dp.message(AddMovie.waiting_for_content)
async def process_add_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data["code"]
    m_type = data["m_type"]
    is_admin = message.from_user.id == ADMIN_ID

    file_id = None
    caption = None

    if m_type == "video":
        if not message.video:
            await message.answer("⚠️ Iltimos, video yuboring!")
            return
        file_id = message.video.file_id
        caption = message.caption or f"🎬 Kino kodi: {code}"
    elif m_type == "photo":
        if not message.photo:
            await message.answer("⚠️ Iltimos, rasm yuboring!")
            return
        file_id = message.photo[-1].file_id
        caption = message.caption or f"🎬 Kino kodi: {code}"
    else:
        if not message.text:
            await message.answer("⚠️ Iltimos, matn yuboring!")
            return
        caption = message.text

    add_movie_db(code, m_type, file_id, caption)

    await message.answer(
        f"✅ <b>Kino muvaffaqiyatli saqlandi!</b>\n🔑 <b>Kod:</b>"
        f" <code>{code}</code>\nFormat: {m_type.upper()}",
        reply_markup=get_main_keyboard(is_admin),
    )
    await state.clear()


# === ADMIN: O'CHIRISH VA KANALLAR ===
@dp.message(F.text == "🗑 Kinoni o'chirish", F.from_user.id == ADMIN_ID)
async def del_movie_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🗑 O'chirmoqchi bo'lgan kino kodini kiriting:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(DeleteMovie.waiting_for_code)


@dp.message(DeleteMovie.waiting_for_code)
async def process_del_code(message: types.Message, state: FSMContext):
    code = (message.text or "").strip()
    if delete_movie_db(code):
        await message.answer(
            f"✅ Kodi <code>{html.escape(code)}</code> bo'lgan kino bazadan"
            " o'chirildi.",
            reply_markup=get_main_keyboard(True),
        )
    else:
        await message.answer(
            "❌ Bunday kodli kino topilmadi.",
            reply_markup=get_main_keyboard(True),
        )
    await state.clear()


@dp.message(F.text == "📢 Kanallarni boshqarish", F.from_user.id == ADMIN_ID)
async def manage_channels(message: types.Message, state: FSMContext):
    await state.clear()
    channels = get_channels_db()
    text = f"📢 <b>Ulangan kanallar soni:</b> {len(channels)}/10\n\n"
    for idx, ch in enumerate(channels, 1):
        text += f"{idx}. {html.escape(ch['name'])} (<code>{ch['chat_id']}</code>)\n"
    text += (
        "\n⚙️ <b>Buyruqlar:</b>\n/addchannel — Kanal qo'shish\n/delchannel —"
        " Kanalni o'chirish"
    )
    await message.answer(text)


@dp.message(Command("addchannel", "add_channel"), F.from_user.id == ADMIN_ID)
async def add_ch_start(message: types.Message, state: FSMContext):
    await state.clear()
    if len(get_channels_db()) >= 10:
        await message.answer("❌ Maksimal 10 ta kanal ulay olasiz!")
        return
    await message.answer(
        "🆔 Kanal ID sini kiriting (masalan: <code>-1001234567890</code>):"
    )
    await state.set_state(AddChannel.waiting_for_id)


@dp.message(AddChannel.waiting_for_id)
async def add_ch_id(message: types.Message, state: FSMContext):
    await state.update_data(chat_id=(message.text or "").strip())
    await message.answer("🔗 Kanal linkini kiriting:")
    await state.set_state(AddChannel.waiting_for_link)


@dp.message(AddChannel.waiting_for_link)
async def add_ch_link(message: types.Message, state: FSMContext):
    await state.update_data(link=(message.text or "").strip())
    await message.answer("🏷 Tugma uchun kanal nomini kiriting:")
    await state.set_state(AddChannel.waiting_for_name)


@dp.message(AddChannel.waiting_for_name)
async def add_ch_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    add_channel_db(data["chat_id"], data["link"], (message.text or "").strip())
    await message.answer("✅ Kanal muvaffaqiyatli qo'shildi!")
    await state.clear()


@dp.message(Command("delchannel", "del_channel"), F.from_user.id == ADMIN_ID)
async def del_ch_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("O'chirmoqchi bo'lgan kanal Chat ID sini kiriting:")
    await state.set_state(DeleteChannel.waiting_for_id)


@dp.message(DeleteChannel.waiting_for_id)
async def del_ch_process(message: types.Message, state: FSMContext):
    delete_channel_db((message.text or "").strip())
    await message.answer("✅ Kanal o'chirildi.")
    await state.clear()


# === FOYDALANUVCHI KODI ===
@dp.message(F.text)
async def handle_user_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not code.isdigit():
        return

    unsub = await check_sub_channels(message.from_user.id)
    if unsub:
        await message.answer(
            "⚠️ Kinoni ko'rish uchun kanallarga a'zo bo'ling:",
            reply_markup=get_sub_keyboard(unsub, code),
        )
        return

    movie = get_movie_db(code)
    if movie:
        await send_movie_to_user(message.chat.id, movie)
    else:
        await message.answer("❌ Ushbu kod bo'yicha hech qanday kino topilmadi.")


async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
