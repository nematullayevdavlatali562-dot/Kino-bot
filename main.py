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
)

from keep_alive import keep_alive

# Server o'chib qolmasligi uchun
keep_alive()

# === SOZLAMALAR ===
BOT_TOKEN = "8957925087:AAEp1epsICBHkOAHUYNi9NauBebhIWJ1aIg"
ADMIN_ID = 6119649341  # O'zingizning Telegram ID-ingiz (raqam)
# ==================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# === SQLITE BAZA SOZLAMALARI ===
def init_db():
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            title TEXT
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


def add_movie_db(code, title):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR REPLACE INTO movies (code, title) VALUES (?, ?)", (code, title)
  )
  conn.commit()
  conn.close()


def get_movie_db(code):
  conn = sqlite3.connect("movies.db")
  cursor = conn.cursor()
  cursor.execute("SELECT title FROM movies WHERE code = ?", (code,))
  row = cursor.fetchone()
  conn.close()
  return row[0] if row else None


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
  waiting_for_title = State()


class DeleteMovie(StatesGroup):
  waiting_for_code = State()


class AddChannel(StatesGroup):
  waiting_for_id = State()
  waiting_for_link = State()
  waiting_for_name = State()


class DeleteChannel(StatesGroup):
  waiting_for_id = State()


# === PASTKI TUGMALAR (REPLY KEYBOARD) ===
def get_main_keyboard(is_admin: bool):
  buttons = [[KeyboardButton(text="🎬 Kino kodi yuborish")]]

  if is_admin:
    buttons.append([
        KeyboardButton(text="➕ Yangi kino qo'shish"),
        KeyboardButton(text="🗑 Kinoni o'chirish"),
    ])
    buttons.append([KeyboardButton(text="📢 Kanallarni boshqarish")])

  return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# === A'ZOLIKNI TEKSHIRISH ===
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
        "🎬 Kino qidirish uchun kodini yuboring yoki quyidagi tugmalardan foydalaning:",
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
      title = get_movie_db(code)
      if title:
        await callback.message.answer(
            f"🎬 **Kino kodi:** `{code}`\n📌 **Kino nomi:** `{title}`",
            parse_mode=ParseMode.MARKDOWN,
        )


@dp.message(F.text == "🎬 Kino kodi yuborish")
async def ask_code_btn(message: types.Message, state: FSMContext):
  await state.clear()
  await message.answer("⌨️ Kino kodini yuboring (masalan: `100`):")


# === ADMIN PANEL TUGMALARI ===


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
  await message.answer("📝 Endi **kino nomi va yilini** yuboring:")
  await state.set_state(AddMovie.waiting_for_title)


@dp.message(AddMovie.waiting_for_title)
async def process_add_title(message: types.Message, state: FSMContext):
  data = await state.get_data()
  code = data["code"]
  title = message.text.strip()

  add_movie_db(code, title)

  await message.answer(
      f"✅ **Kino saqlandi!**\n\n🔑 **Kod:** `{code}`\n🎬 **Nomi:** {title}",
      parse_mode=ParseMode.MARKDOWN,
  )
  await state.clear()


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

  text += "\n⚙️ **Buyruqlar:**\n/add_channel — Kanal qo'shish\n/del_channel — Kanalni o'chirish"
  await message.answer(text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("add_channel"), F.from_user.id == ADMIN_ID)
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


@dp.message(Command("del_channel"), F.from_user.id == ADMIN_ID)
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

  # Agar kiritilgan matn faqat raqamlardan iborat bo'lmasa, uni kino kodi deb hisoblamaydi
  if not code.isdigit():
    return

  unsub = await check_sub_channels(message.from_user.id)
  if unsub:
    await message.answer(
        "⚠️ Kino nomini ko'rish uchun kanallarga a'zo bo'ling:",
        reply_markup=get_sub_keyboard(unsub, code),
    )
    return

  title = get_movie_db(code)
  if title:
    await message.answer(
        f"🎬 **Kino kodi:** `{code}`\n📌 **Kino nomi:** `{title}`\n\n"
        f"🔍 *Nomini nusxalab olib, brauzerdan qidirishingiz mumkin.*",
        parse_mode=ParseMode.MARKDOWN,
    )
  else:
    await message.answer("❌ Ushbu kod bo'yicha hech qanday kino topilmadi.")


async def main():
  print("Bot ishga tushdi...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
