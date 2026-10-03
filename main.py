import asyncio
import os
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
BOT_TOKEN = "8957925087:AAEp1epsICBHkOAHUYNi9NauBebhIWJ1aIg"
ADMIN_ID = 6119649341  # Telegram ID-ingiz
# ==================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Ma'lumotlar bazasi
movies = {}  # {"101": "Avatar: Suv Yo'li (2022)"}
channels = []


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


# === DIZAYN VA TUGMALAR ===


def main_menu_keyboard(is_admin: bool):
  builder = []
  builder.append([
      InlineKeyboardButton(
          text="🔍 Kino izlash", callback_data="search_movie"
      )
  ])

  if is_admin:
    builder.append([
        InlineKeyboardButton(
            text="➕ Kino qoʻshish", callback_data="admin_add_movie"
        ),
        InlineKeyboardButton(
            text="🗑 Oʻchirish", callback_data="admin_del_movie"
        ),
    ])
    builder.append([
        InlineKeyboardButton(
            text="📢 Kanallar boshqaruvi", callback_data="admin_channels"
        )
    ])

  return InlineKeyboardMarkup(inline_keyboard=builder)


async def check_sub_channels(user_id: int):
  unsubscribed = []
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


def sub_keyboard(unsubscribed_channels, code: str = ""):
  kb = []
  for ch in unsubscribed_channels:
    kb.append([InlineKeyboardButton(text=f"➕ {ch['name']}", url=ch["link"])])

  cb_data = f"check_sub:{code}" if code else "check_sub_general"
  kb.append([
      InlineKeyboardButton(
          text="✅ A'zolikni tasdiqlash", callback_data=cb_data
      )
  ])
  return InlineKeyboardMarkup(inline_keyboard=kb)


# === HANDLERLAR ===


@dp.message(Command("start"))
async def start_handler(message: types.Message):
  is_admin = message.from_user.id == ADMIN_ID
  unsub = await check_sub_channels(message.from_user.id)

  if unsub:
    await message.answer(
        "✨ **KinoSearch Botga xush kelibsiz!**\n\n"
        "━━━━━━━ ⚡️ ━━━━━━━\n"
        "Botdan toʻliq foydalanish va kinolarni izlash uchun quyidagi kanallarga obuna boʻling:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=sub_keyboard(unsub),
    )
  else:
    await message.answer(
        f"👋 Assalomu alaykum, **{message.from_user.first_name}**!\n\n"
        "━━━━━━━ 🎬 **KINOSEARCH** ━━━━━━━\n"
        "Oʻzingizga kerakli kino kodini yuboring yoki quyidagi menyudan foydalaning:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(is_admin),
    )


@dp.callback_query(F.data.startswith("check_sub"))
async def check_subscription_callback(callback: types.CallbackQuery):
  unsub = await check_sub_channels(callback.from_user.id)
  if unsub:
    await callback.answer(
        "❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True
    )
  else:
    await callback.answer("✅ Obuna tasdiqlandi!", show_alert=True)
    await callback.message.delete()

    data_parts = callback.data.split(":")
    if len(data_parts) > 1 and data_parts[1]:
      code = data_parts[1]
      if code in movies:
        movie_title = movies[code]
        await callback.message.answer(
            f"🎬 **KINO TOPILDI**\n\n"
            f"📌 **Nomi:** `{movie_title}`\n"
            f"🔑 **Kodi:** `{code}`\n\n"
            f"💡 *Nomini nusxalab olib, brauzer orqali tomosha qilishingiz mumkin.*",
            parse_mode=ParseMode.MARKDOWN,
        )


@dp.callback_query(F.data == "search_movie")
async def search_movie_cb(callback: types.CallbackQuery):
  await callback.answer()
  await callback.message.answer("⌨️ Kino kodini kiriting (masalan: `101`):")


# === ADMIN PANELLI HANDLERLAR ===


@dp.callback_query(F.data == "admin_add_movie", F.from_user.id == ADMIN_ID)
async def add_movie_start(callback: types.CallbackQuery, state: FSMContext):
  await callback.answer()
  await callback.message.answer("✏️ Yangi kino uchun **sonli kod** kiriting:")
  await state.set_state(AddMovie.waiting_for_code)


@dp.message(AddMovie.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
  await state.update_data(code=message.text.strip())
  await message.answer("📝 Endi kino **nomi va yilini** kiriting:")
  await state.set_state(AddMovie.waiting_for_title)


@dp.message(AddMovie.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
  data = await state.get_data()
  code = data["code"]
  title = message.text.strip()
  movies[code] = title

  await message.answer(
      f"✅ **Kino saqlandi!**\n\n🔑 **Kod:** `{code}`\n🎬 **Nomi:** {title}",
      parse_mode=ParseMode.MARKDOWN,
  )
  await state.clear()


@dp.callback_query(F.data == "admin_del_movie", F.from_user.id == ADMIN_ID)
async def del_movie_start(callback: types.CallbackQuery, state: FSMContext):
  await callback.answer()
  await callback.message.answer("🗑 Oʻchirmoqchi boʻlgan kino kodini kiriting:")
  await state.set_state(DeleteMovie.waiting_for_code)


@dp.message(DeleteMovie.waiting_for_code)
async def process_delete_code(message: types.Message, state: FSMContext):
  code = message.text.strip()
  if code in movies:
    del movies[code]
    await message.answer(f"✅ Kod `{code}` boʻlgan kino oʻchirildi.")
  else:
    await message.answer("❌ Bunday kodli kino topilmadi.")
  await state.clear()


@dp.callback_query(F.data == "admin_channels", F.from_user.id == ADMIN_ID)
async def manage_channels(callback: types.CallbackQuery):
  await callback.answer()
  text = f"📢 **Ulangan kanallar:** {len(channels)}/10\n\n"
  for idx, ch in enumerate(channels, 1):
    text += f"{idx}. {ch['name']} (`{ch['chat_id']}`)\n"

  text += "\n⚙️ **Buyruqlar:**\n/add_channel — Kanal qoʻshish\n/del_channel — Kanalni oʻchirish"
  await callback.message.answer(text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("add_channel"), F.from_user.id == ADMIN_ID)
async def add_ch_start(message: types.Message, state: FSMContext):
  if len(channels) >= 10:
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
  channels.append({
      "chat_id": data["chat_id"],
      "link": data["link"],
      "name": message.text.strip(),
  })
  await message.answer("✅ Kanal muvaffaqiyatli qoʻshildi!")
  await state.clear()


@dp.message(Command("del_channel"), F.from_user.id == ADMIN_ID)
async def del_ch_start(message: types.Message, state: FSMContext):
  await message.answer("Oʻchirmoqchi boʻlgan kanal Chat ID sini kiriting:")
  await state.set_state(DeleteChannel.waiting_for_id)


@dp.message(DeleteChannel.waiting_for_id)
async def del_ch_process(message: types.Message, state: FSMContext):
  ch_id = message.text.strip()
  global channels
  channels = [c for c in channels if c["chat_id"] != ch_id]
  await message.answer("✅ Kanal oʻchirildi.")
  await state.clear()


# === FOYDALANUVCHIDAN KOD QABUL QILISH ===


@dp.message(F.text)
async def get_movie(message: types.Message):
  unsub = await check_sub_channels(message.from_user.id)
  code = message.text.strip()

  if unsub:
    await message.answer(
        "⚠️ Kino nomini olish uchun quyidagi kanallarga obuna boʻling:",
        reply_markup=sub_keyboard(unsub, code),
    )
    return

  if code in movies:
    movie_title = movies[code]
    await message.answer(
        f"🎬 **KINO TOPILDI**\n\n"
        f"📌 **Nomi:** `{movie_title}`\n"
        f"🔑 **Kodi:** `{code}`\n\n"
        f"💡 *Nomini nusxalab olib, brauzer orqali tomosha qilishingiz mumkin.*",
        parse_mode=ParseMode.MARKDOWN,
    )
  else:
    await message.answer("❌ Ushbu kod boʻyicha hech qanday kino topilmadi.")


async def main():
  print("Bot zamonaviy dizaynda ishga tushdi...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
