from io import BytesIO

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery

from PIL import Image
from pyzbar.pyzbar import decode

router = Router()

class QRScanState(StatesGroup):
    waiting_for_image = State()

# 1) Команда /scanqr
@router.message(Command("scanqr"))
async def cmd_start_qr_scan(message: Message, state: FSMContext):
    await state.set_state(QRScanState.waiting_for_image)
    await message.answer("📷 Пришлите, пожалуйста, изображение с QR-кодом.")

# 2) Нажатие inline-кнопки с callback_data="scanqr"
@router.callback_query(F.data == "scanqr")
async def qr_scan_callback(query: CallbackQuery, state: FSMContext):
    await query.answer()  # снимаем «часик» на кнопке
    await state.set_state(QRScanState.waiting_for_image)
    await query.message.answer("📷 Пришлите, пожалуйста, изображение с QR-кодом.")

# 3) Обработка фото, когда мы в состоянии waiting_for_image
@router.message(QRScanState.waiting_for_image, F.photo)
async def handle_qr_photo(message: Message, state: FSMContext):
    buffer = BytesIO()
    file_id = message.photo[-1].file_id
    await message.bot.download(file_id, destination=buffer)
    buffer.seek(0)

    img = Image.open(buffer)
    decoded_objs = decode(img)

    if not decoded_objs:
        await message.answer("❌ Не удалось найти QR-код. Попробуйте другое изображение.")
    else:
        qr_data = decoded_objs[0].data.decode('utf-8')
        await message.answer(f"✅ Распознанные данные: <code>{qr_data}</code>")

    await state.clear()

# 4) Если вместо фото пришёл не-photo
@router.message(QRScanState.waiting_for_image, ~F.photo)
async def handle_not_photo(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, пришлите изображение (фото) с QR-кодом.")