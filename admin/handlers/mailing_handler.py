from email.mime import image
import logging
import os

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from aiogram.fsm.context import FSMContext

from admin.keyboards.admin_keyboards import admin_keyboard
from admin.keyboards.inline_keyboards import admin_link_keyboard, mailing_keyboard, accept_mailing_kb
from admin.States.mailing_fsm import MailingFSM
from config import admin_chat_required
from database.models import Mailing
from database.requests import MailingRequests, UserRequests

logger = logging.getLogger(__name__)

admin_mailing_router = Router()

@admin_chat_required
@admin_mailing_router.message(F.text == "📢 Рассылка")
async def start_mailing(message: Message, state: FSMContext):
    """Начало рассылки"""
    await message.answer("Введите текст рассылки:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(MailingFSM.text)
    
@admin_chat_required
@admin_mailing_router.message(MailingFSM.text)
async def get_text_mailing(message: Message, state: FSMContext):
    """Получение текста рассылки"""
    await state.update_data(text=message.text)
    if len(message.text) > 1024:
        await message.answer("Текст записан!\nВы можете выбрать опции для отправки рассылки:\nКартинки не доступны, тк длина текста превышает 1024 символа", reply_markup=await mailing_keyboard(len(message.text)))
        return
    elif len(message.text) > 1 and len(message.text) < 1024:
        await message.answer("Текст записан!\n", reply_markup= await mailing_keyboard(len(message.text)))
        return
    else:
        await message.answer("Текст слишком короткий, введите текст рассылки:", reply_markup=ReplyKeyboardRemove())
        return
    
@admin_chat_required
@admin_mailing_router.callback_query(F.data == "change_text_mailing")
async def change_text_mailing(callback: CallbackQuery, state: FSMContext):
    """Изменение текста рассылки"""
    await callback.message.answer("Введите новый текст рассылки:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(MailingFSM.text)
    await callback.answer()
    return

@admin_chat_required
@admin_mailing_router.callback_query(F.data == "mailing_add_image")
async def add_image_mailing(callback: CallbackQuery, state: FSMContext):
    """Добавление картинки к рассылке"""
    await callback.message.answer("Отправьте картинку для рассылки:")
    await state.set_state(MailingFSM.image)
    await callback.answer()
    return
    
@admin_chat_required
@admin_mailing_router.message(MailingFSM.image)
async def get_image_mailing(message: Message, state: FSMContext):
    """Получение картинки для рассылки"""
    if message.photo:
        await state.update_data(image=message.photo[-1].file_id)
        await message.answer("Картинка добавлена!\nВы можете выбрать опции для отправки рассылки:", reply_markup=await mailing_keyboard(1000))
        await state.set_state(MailingFSM.wait)
    else:
        await message.answer("Это не картинка, попробуйте еще раз:")
    
    return

@admin_chat_required
@admin_mailing_router.callback_query(F.data == "mailing_add_button_url")
async def add_button_url_mailing(callback: CallbackQuery, state: FSMContext):
    """Добавление ссылки для кнопки к рассылке"""
    await callback.message.answer("Отправьте ссылку для кнопки:")
    await state.set_state(MailingFSM.button_url)
    await callback.answer()
    
@admin_chat_required
@admin_mailing_router.message(MailingFSM.button_url)
async def get_button_url_mailing(message: Message, state: FSMContext):
    """Получение ссылки для кнопки к рассылке"""
    link = message.text.split('/')
    if len(link) > 1 and link[0] == "https:" and link[1] == "":
        await state.update_data(button_url=message.text)
        await message.answer("Ссылка добавлена!\nВы можете выбрать опции для отправки рассылки:", reply_markup=await mailing_keyboard(1000))
        await state.set_state(MailingFSM.wait)
    else:
        await message.answer("Это не ссылка, попробуйте еще раз:")
    return

@admin_chat_required
@admin_mailing_router.callback_query(F.data == "send_mailing")
async def sending_mailing(callback: CallbackQuery, state: FSMContext):
    """Подтверждение отправки рассылки"""
    data = await state.get_data()
    text = data.get("text")
    image = data.get("image")
    button_url = data.get("button_url")
    
    if image:
        if button_url:
            await callback.message.answer_photo(photo=image, caption=text, reply_markup=await admin_link_keyboard(button_url))
        else:
            await callback.message.answer_photo(photo=image, caption=text)
    else:
        if button_url:
            await callback.message.answer(text, reply_markup=await admin_link_keyboard(button_url))
        else:
            await callback.message.answer(text)
    
    await callback.message.answer("Вы уверены, что хотите отправить рассылку?", reply_markup=accept_mailing_kb)
    await state.set_state(MailingFSM.wait)

async def download_image(callback: CallbackQuery, image_id: str) -> str:
    """Скачивание картинки"""
    bot = callback.bot
    file = await bot.get_file(image_id)
    file_data = await bot.download_file(file.file_path)

    # Уникальное имя файла
    filename = f"{image_id}.jpg"
    save_path = os.path.join("media", "mailing", "photos", filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Сохраняем файл
    with open(save_path, "wb") as f:
        f.write(file_data.getvalue())

    return f"/media/mailing/photos/{filename}"


@admin_chat_required
@admin_mailing_router.callback_query(F.data == "accept_send_mailing")
async def send_mailing(callback: CallbackQuery, state: FSMContext):
    """Отправка рассылки"""
    data = await state.get_data()
    text = data.get("text")
    image = data.get("image")
    button_url = data.get("button_url")
    
    users = await UserRequests.get_all_users()
    for user in users:
        try:
            if image:
                if button_url:
                    await callback.message.bot.send_photo(chat_id=user.tg_id, photo=image, caption=text, reply_markup=await admin_link_keyboard(button_url))
                else:
                    await callback.message.bot.send_photo(chat_id=user.tg_id, photo=image, caption=text)
            else:
                if button_url:
                    await callback.message.bot.send_message(chat_id=user.tg_id, text=text, reply_markup=await admin_link_keyboard(button_url))
                else:
                    await callback.message.bot.send_message(chat_id=user.tg_id, text=text)
        except Exception as e:
            logger.error(f"Ошибка при отправке рассылки пользователю {user.tg_id}: {e}")
    await callback.message.answer("Рассылка отправлена всем пользователям!")
    image = await download_image(callback, image) if image else None
    await MailingRequests.create_mailing(
        from_user=await UserRequests.get_by_tg_id(callback.from_user.id),
        text=text,
        image=image,
        button_url=button_url,
        type = "other",
    )
    await state.clear()
    
@admin_chat_required
@admin_mailing_router.callback_query(F.data == "cancel_send_mailing")
async def cancel_send_mailing(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    await callback.message.answer("Рассылка отменена!", reply_markup=admin_keyboard)
    await state.clear()
    
