import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
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
BOT_TOKEN = "8957925087:AAEp1epsICBHkOAHUYNi9NauBebhIWJ1aIg"
ADMIN_ID = 6119649341  # O'zingizning Telegram ID-ingiz
# ==================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# === BAZA SOZLAMALARI (SQLite) ===
def init_db():
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  # Content_type: 'text', 'photo', yoki 'video'
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            content_type TEXT,
            file_id TEXT,
            caption TEXT
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            chat_id TEXT PRIMARY KEY,
            link TEXT,
            name TEXT
        )
    """)
  conn.commit()
  conn.close()


init_db()


def add_movie_db(code, content_type, file_id, caption):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR REPLACE INTO movies (code, content_type, file_id, caption)"
      " VALUES (?, ?, ?, ?)",
      (code, content_type, file_id, caption),
  )
  conn.commit()
  conn.close()


def get_movie_db(code):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute(
      "SELECT content_type, file_id, caption FROM movies WHERE code = ?",
      (code,),
  )
  row = cursor.fetchone()
  conn.close()
  if row:
    return {"type": row[0], "file_id": row[1], "caption": row[2]}
  return None


def delete_movie_db(code):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM movies WHERE code = ?", (code,))
  count = cursor.rowcount
  conn.commit()
  conn.close()
  return count > 0


def get_channels_db():
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute("SELECT chat_id, link, name FROM channels")
  rows = cursor.fetchall()
  conn.close()
  return [
      {"chat_id": row[0], "link": row[1], "name": row[2]} for row in rows
  ]


def add_channel_db(chat_id, link, name):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR REPLACE INTO channels (chat_id, link, name) VALUES (?, ?, ?)",
      (chat_id, link, name),
  )
  conn.commit()
  conn.close()


def delete_channel_db(chat_id):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM channels WHERE chat_id = ?", (chat_id,))
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
    buttons.append([
        KeyboardButton(text="➕ Yangi kino qo'shish"),
        KeyboardButton(text="🗑 Kinoni o'chirish"),
    ])
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
  unsubscribed = []
  channels = get_channels_db()
  for ch in channels:
    try:
      member = await bot.get_chat_member(
          chat_id=ch["chat_id"], user_id=user_id
      )
      if member.status in [
          ChatMemberStatus.LEFT,
          ChatMemberStatus.KICKED,
      ]:
        unsubscribed.append(ch)
    except Exception:
      unsubscribed.append(ch)
  return unsubscribed


def get_sub_keyboard(unsubscribed_channels, code: str = ""):
  kb = []
  for ch in unsubscribed_channels:
    kb.append([InlineKeyboardButton(text=f"➕ {ch['name']}", url=ch["link"])])

  cb_data = f"check_sub:{code}" if code else "check_sub_general"
  kb.append([
      InlineKeyboardButton(
          text="✅ A'zolikni tekshirish", callback_data=cb_data
      )
  ])
  return InlineKeyboardMarkup(inline_keyboard=kb)


# === KINO YUBORISH MANTIQI ===
async def send_movie_to_user(chat_id: int, movie_data: dict):
  m_type = movie_data["type"]
  file_id = movie_data["file_id"]
  caption = movie_data["caption"]

  if m_type == "video":
    await bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
  elif m_type == "photo":
    await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
  elif m_type == "text":
    await bot.send_message(chat_id=chat_id, text=caption)


# === BUYRUQLAR VA ASOSIY TUGMALAR ===
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
    await message.answer(
        f"Assalomu alaykum, **{message.from_user.full_name}**!\n\n"
        "🎬 Kino qidirish uchun kodini yuboring yoki quyidagi tugmalardan"
        " foydalaning:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard(is_admin),
    )


@dp.callback_query(F.data.startswith("check_sub"))
async def check_subscription_callback(callback: types.CallbackQuery):
  unsub = await check_sub_channels(callback.from_user.id)
  if unsub:
    await callback.answer(
        "❌ Barcha kanallarga a'zo bo'lmadingiz!", show_alert=True
    )
  else:
    await callback.answer("✅ A'zolik tasdiqlandi!", show_alert=True)
    await callback.message.delete()

    data_parts = callback.data.split(":")
    if len(data_parts) > 1 and data_parts[1]:
      code = data_parts[1]
      movie = get_movie_db(code)
      if movie:
        await send_movie_to_user(callback.from_user.id, movie)


@dp.message(F.text == "🎬 Kino kodi yuborish")
async def ask_code_btn(message: types.Message, state: FSMContext):
  await state.clear()
  await message.answer("⌨️ Kino kodini yuboring (masalan: `100`):")


# === ADMIN PANEL: KINO QO'SHISH (3 HIL FORMATDA) ===
@dp.message(F.text == "➕ Yangi kino qo'shish", F.from_user.id == ADMIN_ID)
async def add_movie_start(message: types.Message, state: FSMContext):
  await state.clear()
  await message.answer(
      "✏️ Yangi kino uchun **sonli kod** kiriting (masalan: `100`):"
  )
  await state.set_state(AddMovie.waiting_for_code)


@dp.message(AddMovie.waiting_for_code)
async def process_add_code(message: types.Message, state: FSMContext):
  code = message.text.strip()
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
  selected_type = message.text
  if selected_type == "📹 Video":
    m_type = "video"
    msg = "📹 Video faylni yuboring (izohiga kino haqida ma'lumot yozishingiz mumkin):"
  elif selected_type == "🖼 Rasm":
    m_type = "photo"
    msg = "🖼 Rasmni yuboring (izohiga kino haqida ma'lumot yozishingiz mumkin):"
  else:
    m_type = "text"
    msg = "📝 Kino haqidagi matnni yuboring:"

  await state.update_data(m_type=m_type)
  await message.answer(msg, reply_markup=ReplyKeyboardRemove())
  await state.set_state(AddMovie.waiting_for_content)


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
  elif m_type == "text":
    if not message.text:
      await message.answer("⚠️ Iltimos, matn yuboring!")
      return
    caption = message.text

  add_movie_db(code, m_type, file_id, caption)

  await message.answer(
      f"✅ **Kino muvaffaqiyatli saqlandi!**\n🔑 **Kod:** `{code}`\nFormat:"
      f" {m_type.upper()}",
      parse_mode=ParseMode.MARKDOWN,
      reply_markup=get_main_keyboard(is_admin),
  )
  await state.clear()


# === ADMIN PANEL: O'CHIRISH VA KANALLAR ===
@dp.message(F.text == "🗑 Kinoni o'chirish", F.from_user.id == ADMIN_ID)
async def del_movie_start(message: types.Message, state: FSMContext):
  await state.clear()
  await message.answer("🗑 O'chirmoqchi bo'lgan kino kodini kiriting:")
  await state.set_state(DeleteMovie.waiting_for_code)


@dp.message(DeleteMovie.waiting_for_code)
async def process_del_code(message: types.Message, state: FSMContext):
  code = message.text.strip()
  if delete_movie_db(code):
    await message.answer(f"✅ Kodi `{code}` bo'lgan kino bazadan o'chirildi.")
  else:
    await message.answer("❌ Bunday kodli kino topilmadi.")
  await state.clear()


@dp.message(F.text == "📢 Kanallarni boshqarish", F.from_user.id == ADMIN_ID)
async def manage_channels(message: types.Message, state: FSMContext):
  await state.clear()
  channels = get_channels_db()
  text = f"📢 **Ulangan kanallar soni:** {len(channels)}/10\n\n"
  for idx, ch in enumerate(channels, 1):
    text += f"{idx}. {ch['name']} (`{ch['chat_id']}`)\n"

  text += "\n⚙️ **Buyruqlar:**\n/addchannel — Kanal qo'shish\n/delchannel — Kanalni o'chirish"
  await message.answer(text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("addchannel", "add_channel"), F.from_user.id == ADMIN_ID)
async def add_ch_start(message: types.Message, state: FSMContext):
  await state.clear()
  if len(get_channels_db()) >= 10:
    await message.answer("❌ Maksimal 10 ta kanal ulay olasiz!")
    return
  await message.answer("🆔 Kanal ID sini kiriting (masalan: `-1001234567890`):")
  await state.set_state(AddChannel.waiting_for_id)


@dp.message(AddChannel.waiting_for_id)
async def add_ch_id(message: types.Message, state: FSMContext):
  await state.update_data(chat_id=message.text.strip())
  await message.answer("🔗 Kanal linkini kiriting:")
  await state.set_state(AddChannel.waiting_for_link)


@dp.message(AddChannel.waiting_for_link)
async def add_ch_link(message: types.Message, state: FSMContext):
  await state.update_data(link=message.text.strip())
  await message.answer("🏷 Tugma uchun kanal nomini kiriting:")
  await state.set_state(AddChannel.waiting_for_name)


@dp.message(AddChannel.waiting_for_name)
async def add_ch_name(message: types.Message, state: FSMContext):
  data = await state.get_data()
  add_channel_db(data["chat_id"], data["link"], message.text.strip())
  await message.answer("✅ Kanal muvaffaqiyatli qo'shildi!")
  await state.clear()


@dp.message(Command("delchannel", "del_channel"), F.from_user.id == ADMIN_ID)
async def del_ch_start(message: types.Message, state: FSMContext):
  await state.clear()
  await message.answer("O'chirmoqchi bo'lgan kanal Chat ID sini kiriting:")
  await state.set_state(DeleteChannel.waiting_for_id)


@dp.message(DeleteChannel.waiting_for_id)
async def del_ch_process(message: types.Message, state: FSMContext):
  delete_channel_db(message.text.strip())
  await message.answer("✅ Kanal o'chirildi.")
  await state.clear()


# === FOYDALANUVCHIDAN RAQAMLI KOD QABUL QILISH ===
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
