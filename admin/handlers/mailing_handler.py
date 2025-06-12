import logging
import os
import aiohttp
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from aiogram.fsm.context import FSMContext
from admin.keyboards.admin_inline import mailing_keyboard, admin_link_keyboard, accept_mailing_kb
from admin.keyboards.admin_reply import admin_keyboard
from data.url import *
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID
from utils.fsm_states import MailingFSM

logger = logging.getLogger(__name__)



admin_mailing_router = Router()
admin_mailing_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin(ADMIN_CHAT_ID, show_message=False)
)


@admin_mailing_router.message(F.text == "📢 Рассылка")
async def start_mailing(message: Message, state: FSMContext):
    """Инициирует процесс создания рассылки.

    Args:
        message (Message): Сообщение от пользователя, инициирующее рассылку.
        state (FSMContext): Контекст состояния FSM для управления процессом.

    Notes:
        Устанавливает состояние MailingFSM.text и удаляет текущую клавиатуру.
    """
    await message.answer("Введите текст рассылки:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(MailingFSM.text)
    

@admin_mailing_router.message(MailingFSM.text)
async def get_text_mailing(message: Message, state: FSMContext):
    """Обрабатывает введённый текст рассылки.

    Args:
        message (Message): Сообщение с текстом рассылки.
        state (FSMContext): Контекст состояния FSM для сохранения данных.

    Notes:
        Сохраняет текст, проверяет длину (максимум 1024 символа) и предлагает опции для продолжения.
    """
    await state.update_data(text=message.text)
    if len(message.text) > 1024:
        await message.answer("Текст записан!\nВы можете выбрать опции для отправки рассылки:\nКартинки не доступны, тк длина текста превышает 1024 символа",
                             reply_markup=await mailing_keyboard(len(message.text)))
        return
    elif len(message.text) > 1 and len(message.text) < 1024:
        await message.answer("Текст записан!\n",
                             reply_markup= await mailing_keyboard(len(message.text)))
        return
    else:
        await message.answer("Текст слишком короткий, введите текст рассылки:",
                             reply_markup=ReplyKeyboardRemove())
        return
    

@admin_mailing_router.callback_query(F.data == "change_text_mailing")
async def change_text_mailing(callback: CallbackQuery, state: FSMContext):
    """Позволяет изменить текст рассылки.

    Args:
        callback (CallbackQuery): Callback-запрос от кнопки "Изменить текст".
        state (FSMContext): Контекст состояния FSM для сброса на состояние текста.

    Notes:
        Устанавливает состояние MailingFSM.text и удаляет текущую клавиатуру.
    """
    await callback.message.answer("Введите новый текст рассылки:",
                                  reply_markup=ReplyKeyboardRemove())
    await state.set_state(MailingFSM.text)
    await callback.answer()
    return


@admin_mailing_router.callback_query(F.data == "mailing_add_image")
async def add_image_mailing(callback: CallbackQuery, state: FSMContext):
    """Запрашивает изображение для рассылки.

    Args:
        callback (CallbackQuery): Callback-запрос от кнопки "Добавить картинку".
        state (FSMContext): Контекст состояния FSM для перехода к состоянию изображения.

    Notes:
        Устанавливает состояние MailingFSM.image.
    """
    await callback.message.answer("Отправьте картинку для рассылки:")
    await state.set_state(MailingFSM.image)
    await callback.answer()
    return
    

@admin_mailing_router.message(MailingFSM.image)
async def get_image_mailing(message: Message, state: FSMContext):
    """Сохраняет отправленное изображение для рассылки.

    Args:
        message (Message): Сообщение с изображением.
        state (FSMContext): Контекст состояния FSM для сохранения file_id.

    Notes:
        Сохраняет file_id последнего фото и переключает состояние на MailingFSM.wait.
    """
    if message.photo:
        await state.update_data(image=message.photo[-1].file_id)
        await message.answer("Картинка добавлена!\nВы можете выбрать опции для отправки рассылки:",
                             reply_markup=await mailing_keyboard(1000))
        await state.set_state(MailingFSM.wait)
    else:
        await message.answer("Это не картинка, попробуйте еще раз:")
    return


@admin_mailing_router.callback_query(F.data == "mailing_add_button_url")
async def add_button_url_mailing(callback: CallbackQuery, state: FSMContext):
    """Запрашивает ссылку для кнопки в рассылке.

    Args:
        callback (CallbackQuery): Callback-запрос от кнопки "Добавить ссылку".
        state (FSMContext): Контекст состояния FSM для перехода к состоянию ссылки.

    Notes:
        Устанавливает состояние MailingFSM.button_url.
    """
    await callback.message.answer("Отправьте ссылку для кнопки:")
    await state.set_state(MailingFSM.button_url)
    await callback.answer()
    

@admin_mailing_router.message(MailingFSM.button_url)
async def get_button_url_mailing(message: Message, state: FSMContext):
    """Проверяет и сохраняет ссылку для кнопки рассылки.

    Args:
        message (Message): Сообщение с текстом ссылки.
        state (FSMContext): Контекст состояния FSM для сохранения URL.

    Notes:
        Проверяет формат URL (начинается с https://) и переключает состояние на MailingFSM.wait.
    """
    link = message.text.split('/')
    if len(link) > 1 and link[0] == "https:" and link[1] == "":
        await state.update_data(button_url=message.text)
        await message.answer("Ссылка добавлена!\nВы можете выбрать опции для отправки рассылки:",
                             reply_markup=await mailing_keyboard(1000))
        await state.set_state(MailingFSM.wait)
    else:
        await message.answer("Это не ссылка, попробуйте еще раз:")
    return


@admin_mailing_router.callback_query(F.data == "send_mailing")
async def sending_mailing(callback: CallbackQuery, state: FSMContext):
    """Подготавливает предварительный просмотр рассылки перед отправкой.

    Args:
        callback (CallbackQuery): Callback-запрос от кнопки "Отправить рассылку".
        state (FSMContext): Контекст состояния FSM для получения данных.

    Notes:
        Отображает текст, изображение и/или кнопку с ссылкой для подтверждения.
    """
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
    
    await callback.message.answer("Вы уверены, что хотите отправить рассылку?",
                                  reply_markup=accept_mailing_kb)
    await callback.answer()
    await state.set_state(MailingFSM.wait)


async def download_image(callback: CallbackQuery, image_id: str) -> str:
    """Скачивает изображение с сервера Telegram и сохраняет на диск.

    Args:
        callback (CallbackQuery): Callback-запрос для доступа к боту.
        image_id (str): ID изображения для скачивания.

    Returns:
        str: Путь к сохранённому файлу.

    Raises:
        Exception: Если произошла ошибка при скачивании или сохранении.
    """
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


@admin_mailing_router.callback_query(F.data == "accept_send_mailing")
async def send_mailing(callback: CallbackQuery, state: FSMContext):
    """Отправляет рассылку всем пользователям через API.

    Args:
        callback (CallbackQuery): Callback-запрос от кнопки "Подтвердить".
        state (FSMContext): Контекст состояния FSM для получения данных.

    Notes:
        Использует API для получения списка пользователей и отправки сообщений с ограничением скорости.
    """
    data = await state.get_data()
    text = data.get("text")
    image_id = data.get("image")
    button_url = data.get("button_url")

    # 1. Получаем список всех пользователей через API
    if not config_settings.BOT_API_KEY:
        logger.error("BOT_API_KEY не установлен")
        await callback.message.answer("⚠️ Ошибка конфигурации сервера")
        await state.clear()
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url_users,
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"API users error: {response.status} - {error}")
                    await callback.message.answer("⚠️ Ошибка при получении списка пользователей")
                    await state.clear()
                    return

                users = await response.json()
                if not isinstance(users, list):
                    logger.error(f"Некорректный формат пользователей: {type(users)}")
                    await callback.message.answer("⚠️ Некорректный формат данных пользователей")
                    await state.clear()
                    return

    except Exception as e:
        logger.error(f"Ошибка при получении пользователей: {e}")
        await callback.message.answer("⚠️ Ошибка соединения с сервером")
        await state.clear()
        return

    if not users:
        await callback.message.answer("ℹ️ Нет пользователей для рассылки")
        await state.clear()
        return

    # 2. Подготовка данных для рассылки
    reply_markup = await admin_link_keyboard(button_url) if button_url else None
    total_users = len(users)
    success = 0
    failed = 0
    failed_users = []

    progress_msg = await callback.message.answer(
        f"🚀 Начата рассылка для {total_users} пользователей...\n"
        f"⏳ Обработано: 0/{total_users}"
    )

    # 3. Отправка сообщений с ограничением скорости и прогрессом
    for index, user in enumerate(users, 1):
        try:
            tg_id = user.get("tg_id")
            if not tg_id:
                logger.error(f"У пользователя отсутствует tg_id: {user}")
                failed += 1
                failed_users.append(f"ID:{user.get('id')} (нет tg_id)")
                continue

            if image_id:
                await callback.bot.send_photo(
                    chat_id=tg_id,
                    photo=image_id,
                    caption=text,
                    reply_markup=reply_markup
                )
            else:
                await callback.bot.send_message(
                    chat_id=tg_id,
                    text=text,
                    reply_markup=reply_markup
                )
            success += 1

            # Обновление прогресса каждые 10% или 20 пользователей
            if index % max(20, total_users // 10) == 0 or index == total_users:
                try:
                    await progress_msg.edit_text(
                        f"🚀 Рассылка в процессе...\n"
                        f"⏳ Обработано: {index}/{total_users}\n"
                        f"✅ Успешно: {success}\n"
                        f"❌ Ошибок: {failed}"
                    )
                except:
                    pass

            # Ограничение скорости (30 сообщений в секунду - лимит Telegram)
            if index % 30 == 0:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Ошибка при отправке пользователю {tg_id}: {e}")
            failed += 1
            failed_users.append(str(tg_id))
            continue

    # 4. Сохраняем рассылку через API
    mailing_data = {
        "text": text,
        "image": await download_image(callback, image_id) if image_id else None,
        "button_url": button_url,
        "type": "other",
        "tg_user_id": callback.from_user.id,
        "total_recipients": total_users,
        "successful_deliveries": success,
        "failed_deliveries": failed
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url_mailing,
                json=mailing_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 201:
                    error = await response.text()
                    logger.error(f"Ошибка сохранения рассылки: {response.status} - {error}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении рассылки: {e}")

    # 5. Отправляем отчет
    try:
        await progress_msg.delete()
    except:
        pass

    report = (
        f"📊 Рассылка завершена!\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Успешно отправлено: {success}\n"
        f"• Не удалось отправить: {failed}"
    )

    if failed > 0:
        failed_samples = ", ".join(failed_users[:10])
        report += f"\n\nНе удалось отправить: {failed_samples}"
        if failed > 10:
            report += f" и ещё {failed - 10}"

    await callback.message.answer(report, reply_markup=admin_keyboard())
    await callback.answer()
    await state.clear()


@admin_mailing_router.callback_query(F.data == "cancel_send_mailing")
async def cancel_send_mailing(callback: CallbackQuery, state: FSMContext):
    """Отменяет процесс создания рассылки.

    Args:
        callback (CallbackQuery): Callback-запрос от кнопки "Отменить".
        state (FSMContext): Контекст состояния FSM для очистки.

    Notes:
        Возвращает админ-клавиатуру после отмены.
    """
    await callback.message.answer("Рассылка отменена!",
                                  reply_markup=admin_keyboard())
    await callback.answer()
    await state.clear()
    
