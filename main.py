import asyncio
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatMemberStatus
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

# Flask serverini fonda yurgizish (Render uchun)
from keep_alive import keep_alive

keep_alive()

# === ASOSIY SOZLAMALAR ===
BOT_TOKEN = "8957925087:AAEp1epsICBHkOAHUYNi9NauBebhIWJ1aIg"
ADMIN_ID = 6119649341  # O'zingizning Telegram ID-ingiz
# =========================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Ma'lumotlar bazasi (Xotirada)
movies = {}  # {"kino_kodi": "file_id"}
# Kanallar ro'yxati: [{"chat_id": "-100xxx", "link": "https://t.me/xxx", "name": "Kanal 1"}]
channels = []


class AddMovie(StatesGroup):
  waiting_for_code = State()
  waiting_for_video = State()


class DeleteMovie(StatesGroup):
  waiting_for_code = State()


class AddChannel(StatesGroup):
  waiting_for_id = State()
  waiting_for_link = State()
  waiting_for_name = State()


class DeleteChannel(StatesGroup):
  waiting_for_id = State()


# Asosiy tugmalar
def get_main_keyboard(is_admin: bool):
  buttons = [
      [KeyboardButton(text='🎬 Kino kodi yuborish')],
      [KeyboardButton(text="❌ Klaviatura o'chirish")],
  ]
  if is_admin:
    buttons.insert(0, [KeyboardButton(text='➕ Yangi kino qoʻshish')])
    buttons.append([KeyboardButton(text='🗑 Kinoni oʻchirish')])
    buttons.append([KeyboardButton(text='📢 Kanallarni boshqarish')])

  return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# Majburiy obuna tugmalari
async def check_sub_channels(user_id: int):
  unsubscribed = []
  for ch in channels:
    try:
      member = await bot.get_chat_member(
          chat_id=ch['chat_id'], user_id=user_id
      )
      if member.status in [
          ChatMemberStatus.LEFT,
          ChatMemberStatus.KICKED,
      ]:
        unsubscribed.append(ch)
    except Exception:
      # Agar bot kanalda admin bo'lmasa yoki xatolik bo'lsa
      unsubscribed.append(ch)
  return unsubscribed


def get_sub_keyboard(unsubscribed_channels, code: str = ''):
  keyboard = []
  for ch in unsubscribed_channels:
    keyboard.append([InlineKeyboardButton(text=ch['name'], url=ch['link'])])

  cb_data = f'check_sub:{code}' if code else 'check_sub_general'
  keyboard.append([
      InlineKeyboardButton(
          text="✅ A'zolikni tekshirish", callback_data=cb_data
      )
  ])
  return InlineKeyboardMarkup(inline_keyboard=keyboard)


# --- HANDLERLAR ---


@dp.message(Command('start'))
async def start_handler(message: types.Message):
  is_admin = message.from_user.id == ADMIN_ID
  kb = get_main_keyboard(is_admin)

  unsub = await check_sub_channels(message.from_user.id)
  if unsub:
    sub_kb = get_sub_keyboard(unsub)
    await message.answer(
        '⚠️ Botdan foydalanish uchun quyidagi kanallarga a’zo boʻling:',
        reply_markup=sub_kb,
    )
  else:
    await message.answer(
        f"Assalomu alaykum, {message.from_user.full_name}!\n\n🎬 Kino koʻrish uchun kino kodini yuboring.",
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith('check_sub'))
async def check_subscription_callback(
    callback: types.CallbackQuery, state: FSMContext
):
  unsub = await check_sub_channels(callback.from_user.id)
  if unsub:
    await callback.answer(
        "❌ Barcha kanallarga a'zo bo'lmadingiz!", show_alert=True
    )
  else:
    await callback.answer("✅ Rahmat! A'zolik tasdiqlandi.", show_alert=True)
    await callback.message.delete()

    data_parts = callback.data.split(':')
    if len(data_parts) > 1 and data_parts[1]:
      code = data_parts[1]
      if code in movies:
        await callback.message.answer_video(
            video=movies[code], caption=f'🎬 Siz soʻragan kino (Kodi: {code})'
        )


# Klaviatura o'chirish
@dp.message(F.text == "❌ Klaviatura o'chirish")
async def remove_keyboard(message: types.Message):
  await message.answer(
      'Klaviatura oʻchirildi. Qayta chiqarish uchun /start bosing.',
      reply_markup=ReplyKeyboardRemove(),
  )


@dp.message(F.text == '🎬 Kino kodi yuborish')
async def ask_code_info(message: types.Message):
  await message.answer(
      'Kino kodini raqamlar bilan yozib yuboring (masalan: 101):'
  )


# --- ADMIN: KINO QO'SHISH ---
@dp.message(F.text == '➕ Yangi kino qoʻshish', F.from_user.id == ADMIN_ID)
async def add_movie_start(message: types.Message, state: FSMContext):
  await message.answer('Yangi kino uchun **sonli kod** kiriting (masalan: 101):')
  await state.set_state(AddMovie.waiting_for_code)


@dp.message(AddMovie.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
  code = message.text.strip()
  await state.update_data(code=code)
  await message.answer(f'Kino kodi **{code}** deb saqlandi.\nEndi videoni yuboring:')
  await state.set_state(AddMovie.waiting_for_video)


@dp.message(AddMovie.waiting_for_video, F.video)
async def process_video(message: types.Message, state: FSMContext):
  data = await state.get_data()
  code = data['code']
  movies[code] = message.video.file_id
  await message.answer(
      f'✅ Kino muvaffaqiyatli saqlandi!\nKodi: **{code}**'
  )
  await state.clear()


# --- ADMIN: KINONI O'CHIRISH ---
@dp.message(F.text == '🗑 Kinoni oʻchirish', F.from_user.id == ADMIN_ID)
async def delete_movie_start(message: types.Message, state: FSMContext):
  await message.answer('Oʻchirmoqchi boʻlgan kino kodini kiriting:')
  await state.set_state(DeleteMovie.waiting_for_code)


@dp.message(DeleteMovie.waiting_for_code)
async def process_delete_code(message: types.Message, state: FSMContext):
  code = message.text.strip()
  if code in movies:
    del movies[code]
    await message.answer(f'✅ Kodi **{code}** boʻlgan kino oʻchirib tashlandi.')
  else:
    await message.answer('❌ Bunday kodli kino topilmadi.')
  await state.clear()


# --- ADMIN: KANALLARNI BOSHQARISH ---
@dp.message(F.text == '📢 Kanallarni boshqarish', F.from_user.id == ADMIN_ID)
async def manage_channels(message: types.Message):
  text = f"📢 **Ulangan kanallar soni:** {len(channels)}/10\n\n"
  for idx, ch in enumerate(channels, 1):
    text += f"{idx}. {ch['name']} (ID: `{ch['chat_id']}`)\n"

  text += '\nBuyruqlar:\n/add_channel - Kanal qoʻshish\n/del_channel - Kanalni oʻchirish'
  await message.answer(text, parse_mode='Markdown')


@dp.message(Command('add_channel'), F.from_user.id == ADMIN_ID)
async def add_ch_start(message: types.Message, state: FSMContext):
  if len(channels) >= 10:
    await message.answer('❌ Maksimal 10 ta kanal qoʻshish mumkin!')
    return
  await message.answer(
      "Kanal ID sini kiriting (masalan: `-1001234567890`).\n\n⚠️ **Eslatmalaringiz:** Bot ushbu kanalda **Admin** bo'lishi shart!"
  )
  await state.set_state(AddChannel.waiting_for_id)


@dp.message(AddChannel.waiting_for_id)
async def add_ch_id(message: types.Message, state: FSMContext):
  await state.update_data(chat_id=message.text.strip())
  await message.answer(
      "Kanalga kirish havolasini (link) kiriting (masalan: `https://t.me/kanal_linki`):"
  )
  await state.set_state(AddChannel.waiting_for_link)


@dp.message(AddChannel.waiting_for_link)
async def add_ch_link(message: types.Message, state: FSMContext):
  await state.update_data(link=message.text.strip())
  await message.answer(
      "Tugma uchun kanal nomini kiriting (masalan: `1-Kanalga a'zo bo'lish`):"
  )
  await state.set_state(AddChannel.waiting_for_name)


@dp.message(AddChannel.waiting_for_name)
async def add_ch_name(message: types.Message, state: FSMContext):
  data = await state.get_data()
  channels.append({
      'chat_id': data['chat_id'],
      'link': data['link'],
      'name': message.text.strip(),
  })
  await message.answer("✅ Kanal muvaffaqiyatli qo'shildi!")
  await state.clear()


@dp.message(Command('del_channel'), F.from_user.id == ADMIN_ID)
async def del_ch_start(message: types.Message, state: FSMContext):
  await message.answer(
      "O'chirmoqchi bo'lgan kanalingizning Chat ID sini kiriting:"
  )
  await state.set_state(DeleteChannel.waiting_for_id)


@dp.message(DeleteChannel.waiting_for_id)
async def del_ch_process(message: types.Message, state: FSMContext):
  ch_id = message.text.strip()
  global channels
  channels = [c for c in channels if c['chat_id'] != ch_id]
  await message.answer("✅ Kanal o'chirildi.")
  await state.clear()


# --- FOYDALANUVCHIDAN KINO KODI QABUL QILISH ---
@dp.message(F.text)
async def get_movie(message: types.Message):
  unsub = await check_sub_channels(message.from_user.id)
  code = message.text.strip()

  if unsub:
    sub_kb = get_sub_keyboard(unsub, code)
    await message.answer(
        '⚠️ Kinoni koʻrish uchun avval kanallarga a’zo boʻling:',
        reply_markup=sub_kb,
    )
    return

  if code in movies:
    await message.answer_video(
        video=movies[code], caption=f'🎬 Siz soʻragan kino (Kodi: {code})'
    )
  else:
    await message.answer('❌ Ushbu kod boʻyicha kino topilmadi.')


async def main():
  print('Bot ishga tushdi...')
  await dp.start_polling(bot)


if __name__ == '__main__':
  asyncio.run(main())
