import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keep_alive import keep_alive

keep_alive()

# === SOZLAMALAR ===
BOT_TOKEN = "BOT_TOKENINGIZNI_SHUYERGA_YOZING"
ADMIN_ID = 123456789  # O'zingizning Telegram ID-ingiz
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
  rows = cursor.rowcount
  conn.commit()
  conn.close()
  return rows > 0


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


# === HOLATLAR (STATES) ===
class SearchMovie(StatesGroup):
  waiting_for_code = State()


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


# === MENYU TUGMALARI ===
def get_main_keyboard(is_admin: bool):
  kb = [[
      InlineKeyboardButton(
          text="🔍 Kino kodini yuborish", callback_data="start_search"
      )
  ]]
  if is_admin:
    kb.append([
        InlineKeyboardButton(
            text="➕ Kino qoʻshish", callback_data="admin_add_movie"
        ),
        InlineKeyboardButton(
            text="🗑 Kinoni oʻchirish", callback_data="admin_del_movie"
        ),
    ])
    kb.append([
        InlineKeyboardButton(
            text="📢 Kanallarni boshqarish", callback_data="admin_channels"
        )
    ])
  return InlineKeyboardMarkup(inline_keyboard=kb)


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


# === HANDLERLAR ===
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
  await state.clear()
  is_admin = message.from_user.id == ADMIN_ID
  unsub = await check_sub_channels(message.from_user.id)

  if unsub:
    await message.answer(
        "⚠️ Botdan foydalanish uchun quyidagi kanallarga a’zo boʻling:",
        reply_markup=get_sub_keyboard(unsub),
    )
  else:
    await message.answer(
        f"Assalomu alaykum, **{message.from_user.full_name}**!\n\n"
        "🎬 **KinoSearch** botiga xush kelibsiz. Quyidagi tugma orqali kino kodini kiriting:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard(is_admin),
    )


@dp.callback_query(F.data.startswith("check_sub"))
async def check_subscription_callback(
    callback: types.CallbackQuery, state: FSMContext
):
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
            f"🎬 **Kino kodi:** `{code}`\n📌 **Kino nomi:** `{title}`\n\n"
            f"🔍 *Nomini nusxalab olib, brauzerdan qidirishingiz mumkin.*",
            parse_mode=ParseMode.MARKDOWN,
        )


@dp.callback_query(F.data == "start_search")
async def start_search_cb(callback: types.CallbackQuery, state: FSMContext):
  await callback.answer()
  await callback.message.answer(
      "⌨️ Kino kodini yuboring (masalan: `100`):", parse_mode=ParseMode.MARKDOWN
  )
  await state.set_state(SearchMovie.waiting_for_code)


@dp.message(SearchMovie.waiting_for_code)
async def process_search_code(message: types.Message, state: FSMContext):
  unsub = await check_sub_channels(message.from_user.id)
  code = message.text.strip()

  if unsub:
    await message.answer(
        "⚠️ Kino nomini koʻrish uchun kanallarga a’zo boʻling:",
        reply_markup=get_sub_keyboard(unsub, code),
    )
    await state.clear()
    return

  title = get_movie_db(code)
  if title:
    await message.answer(
        f"🎬 **Kino kodi:** `{code}`\n📌 **Kino nomi:** `{title}`\n\n"
        f"🔍 *Nomini nusxalab olib, brauzerdan qidirishingiz mumkin.*",
        parse_mode=ParseMode.MARKDOWN,
    )
  else:
    await message.answer("❌ Ushbu kod boʻyicha hech qanday kino topilmadi.")

  await state.clear()


# === ADMIN HANDLERLARI ===
@dp.callback_query(F.data == "admin_add_movie", F.from_user.id == ADMIN_ID)
async def add_movie_cb(callback: types.CallbackQuery, state: FSMContext):
  await callback.answer()
  await callback.message.answer(
      "✏️ Yangi kino uchun **sonli kod** kiriting (masalan: `100`):",
      parse_mode=ParseMode.MARKDOWN,
  )
  await state.set_state(AddMovie.waiting_for_code)


@dp.message(AddMovie.waiting_for_code)
async def process_add_code(message: types.Message, state: FSMContext):
  await state.update_data(code=message.text.strip())
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


@dp.callback_query(F.data == "admin_del_movie", F.from_user.id == ADMIN_ID)
async def del_movie_cb(callback: types.CallbackQuery, state: FSMContext):
  await callback.answer()
  await callback.message.answer(
      "🗑 Oʻchirmoqchi boʻlgan kino kodini kiriting:"
  )
  await state.set_state(DeleteMovie.waiting_for_code)


@dp.message(DeleteMovie.waiting_for_code)
async def process_del_code(message: types.Message, state: FSMContext):
  code = message.text.strip()
  if delete_movie_db(code):
    await message.answer(f"✅ Kodi `{code}` boʻlgan kino bazadan oʻchirildi.")
  else:
    await message.answer("❌ Bunday kodli kino topilmadi.")
  await state.clear()


@dp.callback_query(F.data == "admin_channels", F.from_user.id == ADMIN_ID)
async def manage_channels_cb(callback: types.CallbackQuery):
  await callback.answer()
  channels = get_channels_db()
  text = f"📢 **Ulangan kanallar soni:** {len(channels)}/10\n\n"
  for idx, ch in enumerate(channels, 1):
    text += f"{idx}. {ch['name']} (`{ch['chat_id']}`)\n"

  text += "\n⚙️ **Buyruqlar:**\n/add_channel — Kanal qoʻshish\n/del_channel — Kanalni oʻchirish"
  await callback.message.answer(text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("add_channel"), F.from_user.id == ADMIN_ID)
async def add_ch_start(message: types.Message, state: FSMContext):
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
  await message.answer("✅ Kanal muvaffaqiyatli qoʻshildi!")
  await state.clear()


@dp.message(Command("del_channel"), F.from_user.id == ADMIN_ID)
async def del_ch_start(message: types.Message, state: FSMContext):
  await message.answer("Oʻchirmoqchi boʻlgan kanal Chat ID sini kiriting:")
  await state.set_state(DeleteChannel.waiting_for_id)


@dp.message(DeleteChannel.waiting_for_id)
async def del_ch_process(message: types.Message, state: FSMContext):
  delete_channel_db(message.text.strip())
  await message.answer("✅ Kanal oʻchirildi.")
  await state.clear()


async def main():
  print("Bot ishga tushdi...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
