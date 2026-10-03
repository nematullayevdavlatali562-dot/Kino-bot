import asyncio
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# Flask serverini fonda yurgizish (Render uchun)
from keep_alive import keep_alive

keep_alive()

# === SHU YERGA O'ZINGIZNING MA'LUMOTLARINGIZNI YOZING ===
BOT_TOKEN = "8957925087:AAEp1epsICBHkOAHUYNi9NauBebhIWJ1aIg"
ADMIN_ID = 6119649341 # O'zingizning Telegram ID-ingiz
# ======================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

movies = {}


class AddMovie(StatesGroup):
  waiting_for_code = State()
  waiting_for_video = State()


# Asosiy klaviatura tugmalari
def get_main_keyboard(is_admin: bool):
  buttons = [
      [KeyboardButton(text='🎬 Kino kodi yuborish')],
      [KeyboardButton(text="❌ Klaviatura o'chirish")],
  ]
  if is_admin:
    buttons.insert(0, [KeyboardButton(text='➕ Yangi kino qoʻshish')])

  return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


@dp.message(Command('start'))
async def start_handler(message: types.Message):
  is_admin = message.from_user.id == ADMIN_ID
  kb = get_main_keyboard(is_admin)

  text = (
      f"Assalomu alaykum, {message.from_user.full_name}!\n\n"
      '🎬 Kino koʻrish uchun kino kodini yuboring (masalan: 101).'
  )
  await message.answer(text, reply_markup=kb)


# Klaviatura o'chirish tugmasi bosilganda
@dp.message(F.text == "❌ Klaviatura o'chirish")
async def remove_keyboard(message: types.Message):
  await message.answer(
      'Klaviatura oʻchirildi. Qayta chiqarish uchun /start bosing.',
      reply_markup=ReplyKeyboardRemove(),
  )


# Kino kodi yuborish tugmasi bosilganda
@dp.message(F.text == '🎬 Kino kodi yuborish')
async def ask_code_info(message: types.Message):
  await message.answer(
      'Kino kodini raqamlar bilan yozib yuboring (masalan: 101):'
  )


# Admin uchun kino qo'shish
@dp.message(F.text == '➕ Yangi kino qoʻshish', F.from_user.id == ADMIN_ID)
@dp.message(Command('add'), F.from_user.id == ADMIN_ID)
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
  file_id = message.video.file_id

  movies[code] = file_id
  await message.answer(
      f'✅ Kino muvaffaqiyatli saqlandi!\nKodi: **{code}**'
  )
  await state.clear()


# Kod orqali kinoni topish
@dp.message(F.text)
async def get_movie(message: types.Message):
  code = message.text.strip()
  if code in movies:
    video_id = movies[code]
    await message.answer_video(
        video=video_id, caption=f'🎬 Siz soʻragan kino (Kodi: {code})'
    )
  else:
    await message.answer('❌ Ushbu kod boʻyicha kino topilmadi.')


async def main():
  print('Bot ishga tushdi...')
  await dp.start_polling(bot)


if __name__ == '__main__':
  asyncio.run(main())
