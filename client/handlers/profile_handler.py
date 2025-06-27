import logging

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import F
import aiohttp

from data.config import config_settings
from data.url import url_subscription, url_loyalty
from client.keyboards.inline import (
    get_profile_inline_kb,
    build_interests_keyboard,
    no_user_data_inline_kb,
    user_data_inline_kb,
    bonus_data_inline_kb,
    subscription_data_inline_kb,
    get_subscriptions_name
)

from client.keyboards.reply import main_kb, edit_data_keyboard
from client.services.loyalty import fetch_loyalty_card
from client.services.user import update_user_data
from client.services.subscriptions import get_my_subscriptions, get_subscriptions_data
from utils.validators import name_pattern, email_pattern
from utils.client_utils import get_bonus_word_form, normalize_phone_number, parse_birth_date

logger = logging.getLogger(__name__)

profile_router = Router()

class EditUserData(StatesGroup):
    choosing_field = State()
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_birth_date = State()
    waiting_for_phone = State()
    waiting_for_email = State()


# FSM для редактирования подписок
class EditSubscriptions(StatesGroup):
    choosing = State()


# Обработчик: Вернуться к основному меню (inline)
@profile_router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery):
    await callback.message.answer(
        "Вы вернулись в главное меню.", reply_markup=main_kb
    )
    await callback.answer()


# Обработчик: Вернуться к основному меню (reply)
@profile_router.message(F.text == "Вернуться")
async def handle_back_text(message: types.Message):
    await message.answer(
        "Вы вернулись в главное меню.",
        reply_markup=main_kb
    )


# Хендлер для кнопки "Личный кабинет"
@profile_router.message(F.text == "Личный кабинет")
async def handle_profile(message: Message):
    """
    Обрабатывает запрос пользователя на просмотр профиля.
    Аргументы:
        message (Message): Объект сообщения от пользователя.
    Описание:
        Отправляет пользователю приветственное сообщение и отображает
        клавиатуру профиля. В случае возникновения ошибки логирует её
        и уведомляет пользователя о проблеме.
    """
    
    try:
        temp_message = await message.answer("...", reply_markup=ReplyKeyboardRemove())
        await message.answer(
            "Добро пожаловать в личный кабинет.",
            reply_markup=await get_profile_inline_kb()
        )
        await temp_message.delete()
    except Exception as e:
        logging.error(f"Error handling profile request: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка, попробуйте позже")


# Хендлер для кнопки "Мои данные"
@profile_router.callback_query(F.data == "my_data")
async def my_data_handler(callback: CallbackQuery):
    """
    Обрабатывает запрос пользователя на просмотр своих данных профиля в системе лояльности.
    Аргументы:
        callback (CallbackQuery): Объект запроса обратного вызова от пользователя Telegram.
    Описание:
        - Получает идентификатор пользователя из запроса.
        - Проверяет наличие карты лояльности пользователя.
        - Если карта не найдена, отправляет сообщение о незарегистрированном пользователе с соответствующей клавиатурой.
        - Если карта найдена, формирует и отправляет сообщение с персональными данными пользователя и клавиатурой.
        - Обрабатывает исключение TelegramBadRequest, игнорируя ошибку "message is not modified" и логируя другие ошибки.
    """

    user_id = callback.from_user.id
    await callback.answer()

    card =  await fetch_loyalty_card(user_id)

    try:
        if not card:
            await callback.message.answer(
                "Вы не зарегистрированы в системе лояльности",
                reply_markup=await no_user_data_inline_kb()
            )
            return
        
        user_data_message = (
            f"<b>Ваши данные:</b>\n\n"
            f"Имя: {card.get('user_first_name')}\n"
            f"Фамилия: {card.get('user_last_name')}\n"
            f"Дата рождения: {card.get('birth_date')}\n"
            f"Телефон: {card.get('phone_number')}\n"
            f"Email: {card.get('email')}\n\n"
        )

        await callback.message.answer(
            user_data_message,
            reply_markup=await user_data_inline_kb(),
        )

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.debug(f"Ignored 'message not modified' for user {callback.from_user.id}")
        else:
            logging.error(f"TelegramBadRequest: {e}")
            await callback.answer()
            raise

# Обработчик: Выбор изменения данных пользователя
@profile_router.callback_query(F.data == "change_user_data")
async def change_user_data_menu(callback: types.CallbackQuery):
    await callback.message.answer(
        "Выберите, что Вы хотите изменить:", reply_markup=edit_data_keyboard
    )
    await callback.answer()


# Обработчик: Изменение имени
@profile_router.message(F.text == "Изменить имя")
async def edit_first_name(message: Message, state: FSMContext):
    await message.answer("Введите новое имя:")
    await state.set_state(EditUserData.waiting_for_first_name)


# Обработчик: Изменение фамилии
@profile_router.message(F.text == "Изменить фамилию")
async def edit_last_name(message: Message, state: FSMContext):
    await message.answer("Введите новую фамилию:") 
    await state.set_state(EditUserData.waiting_for_last_name)


# Обработчик: Изменения даты рождения
@profile_router.message(F.text == "Изменить дату рождения")
async def edit_birth_date(message: Message, state: FSMContext):
    await message.answer("Введите новую дату рождения (в формате ГГГГ-ММ-ДД):")
    await state.set_state(EditUserData.waiting_for_birth_date)


# Обработчик: Изменения номера телефона
@profile_router.message(F.text == "Изменить номер телефона")
async def edit_phone(message: Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Введите ваш номер телефона или нажмите кнопку ниже:",
        reply_markup=keyboard
    )
    await state.set_state(EditUserData.waiting_for_phone)


# Обработчик: Изменение почты
@profile_router.message(F.text == "Изменить email")
async def edit_email(message: Message, state: FSMContext):
    await message.answer("Введите новый email:")
    await state.set_state(EditUserData.waiting_for_email)


# Обрабатывает ввод имени пользователя, проверяет его на соответствие шаблону и обновляет данные пользователя.
@profile_router.message(EditUserData.waiting_for_first_name)
async def process_first_name(message: Message, state: FSMContext):
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Имя должно содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return
    
    await update_user_data(user_id=message.from_user.id, first_name=message.text, last_name=None, birth_date=None, phone_number=None, email=None)
    await message.answer("Имя обновлено.")
    await state.clear()


# Обрабатывает ввод фамилии пользователя, проверяет корректность ввода и обновляет данные пользователя в базе.
@profile_router.message(EditUserData.waiting_for_last_name)
async def process_last_name(message: Message, state: FSMContext):
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Фамилия должна содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return

    await update_user_data(user_id=message.from_user.id, first_name=None, last_name=message.text, birth_date=None, phone_number=None, email=None)
    await message.answer("Фамилия обновлена.")
    await state.clear()


# Обрабатывает ввод даты рождения пользователя, проверяет корректность ввода и обновляет данные пользователя в базе.
@profile_router.message(EditUserData.waiting_for_birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    parsed_date = parse_birth_date(message.text)
    if not parsed_date:
        await message.answer("⚠️ Неверный формат. Попробуйте снова (ДД.ММ.ГГГГ):")
        return
    
    await update_user_data(user_id=message.from_user.id, first_name=None, last_name=None, birth_date=parsed_date, phone_number=None, email=None)
    await message.answer("Дата рождения обновлена.")
    await state.clear()


# Обрабатывает ввод номера телефона пользователя, проверяет корректность ввода и обновляет данные пользователя в базе.
@profile_router.message(EditUserData.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()

    normalized_phone = normalize_phone_number(phone)
    if not normalized_phone:
        await message.answer(
            "⚠️ Введите корректный номер телефона с кодом страны, например: +79001234567",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    await update_user_data(user_id=message.from_user.id, first_name=None, last_name=None, birth_date=None, phone_number=normalized_phone, email=None)
    await message.answer("Номер телефона обновлён.", reply_markup=edit_data_keyboard)
    await state.clear()


# Обрабатывает ввод почты пользователя, проверяет корректность ввода и обновляет данные пользователя в базе.
@profile_router.message(EditUserData.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    if not email_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Неверный формат email. Попробуйте снова:")
        return
    
    await update_user_data(user_id=message.from_user.id, first_name=None, last_name=None, birth_date=None, phone_number=None, email=message.text)
    await message.answer("Email обновлён.")
    await state.clear()


# Хендлер для кнопки "Мои подписки"
@profile_router.callback_query(F.data == "my_subscriptions")
async def my_subscriptions_handler(callback: CallbackQuery):
    """
    Обрабатывает запрос пользователя на просмотр его подписок.
    Аргументы:
        callback (CallbackQuery): Объект колбэка от пользователя.
    Описание:
        Получает список активных подписок пользователя и отправляет сообщение с их перечнем.
        Если подписок нет, информирует пользователя об этом.
        В случае ошибки TelegramBadRequest с текстом "message is not modified" — игнорирует её,
        иначе логирует и пробрасывает исключение дальше.
        В конце всегда отправляет ответ на callback для предотвращения зависания интерфейса.
    """
    
    try:
        subscriptions = await get_my_subscriptions(callback.from_user.id)
        if not subscriptions:
            user_data_message = "У вас пока нет активных подписок."
        else:
            subscriptions_list = "\n".join(f"{i+1}. {name}" for i, name in enumerate(subscriptions))
            user_data_message = (
                f"<b>Ваши подписки:</b>\n\n"
                f"{subscriptions_list}"
            )
        await callback.message.answer(
            user_data_message,
            reply_markup=await subscription_data_inline_kb()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.debug(f"Ignored 'message not modified' for user {callback.from_user.id}")
        else:
            logging.error(f"TelegramBadRequest: {e}")
            raise
    finally:
        await callback.answer()


# Хендлер для кнопки "Изменить подписки"
@profile_router.callback_query(F.data == "edit_subscriptions")
async def edit_subscriptions_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает начало процесса редактирования подписок пользователя.
    Аргументы:
        callback (CallbackQuery): Объект колбэка от пользователя.
        state (FSMContext): Контекст конечного автомата состояний для хранения данных пользователя.
    Описание:
        - Получает текущие подписки пользователя.
        - Получает список всех доступных подписок.
        - Сохраняет текущие подписки в состояние FSM.
        - Формирует клавиатуру с отмеченными текущими подписками.
        - Отправляет пользователю сообщение с клавиатурой для выбора подписок.
        - В случае ошибки логирует её и уведомляет пользователя.
    """
    try:
        # Получаем текущие подписки пользователя
        current_subscriptions = await get_my_subscriptions(callback.from_user.id)
        
        # Получаем все доступные подписки
        available_subscriptions = await get_subscriptions_name()
        
        # Сохраняем текущие подписки в состояние
        await state.set_state(EditSubscriptions.choosing)
        await state.update_data(selected=current_subscriptions)

        # Формируем клавиатуру с отмеченными текущими подписками
        markup = await build_interests_keyboard(current_subscriptions)

        await callback.message.answer(
            "Выберите подписки, которые хотите оставить или добавить:\n"
            "Нажмите 'Готово', чтобы сохранить изменения.",
            reply_markup=markup
        )
    except Exception as e:
        logging.error(f"Ошибка при начале редактирования подписок: {e}")
        await callback.message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=await get_profile_inline_kb()
        )
    finally:
        await callback.answer()


@profile_router.callback_query(EditSubscriptions.choosing)
async def process_edit_choice(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор и изменение подписок пользователя в профиле.
    Функция реагирует на нажатия inline-кнопок в меню редактирования подписок:
    - Если пользователь завершает выбор ("done"), функция сравнивает выбранные и текущие подписки, подписывает на новые и отписывает от снятых через API-запросы.
    - Если пользователь выбирает или снимает отдельную подписку, обновляет состояние и клавиатуру выбора.
    Аргументы:
        callback (CallbackQuery): Объект колбэка от Telegram, содержащий данные о нажатой кнопке.
        state (FSMContext): Контекст состояния FSM для хранения и обновления выбранных подписок.
    Исключения:
        При ошибках API или других сбоях информирует пользователя и выводит ошибку в консоль.
    """

    data = await state.get_data()
    selected = data.get("selected", [])

    # Получаем список всех доступных подписок
    available_options = await get_subscriptions_name()

    if callback.data == "done":
        if not selected:
            await callback.answer("Вы ничего не выбрали!")
            return
        
        try:
            # Получаем текущие подписки пользователя
            current_subscriptions = await get_my_subscriptions(callback.from_user.id)
            
            # Получаем данные подписок (id и name)
            subscriptions = await get_subscriptions_data()
            name_to_id = {sub["name"]: sub["id"] for sub in subscriptions}

            headers = {
                "X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()
            }
            user_id = str(callback.from_user.id)

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # Подписываемся на новые подписки
                for name in selected:
                    if name not in current_subscriptions:
                        subscription_id = name_to_id.get(name)
                        if subscription_id:
                            async with session.post(
                                url=f"{url_subscription}{subscription_id}/subscribe/",
                                headers=headers,
                                json={"tg_id": user_id}
                            ) as response:
                                if response.status != 200:
                                    print(f"Ошибка при подписке на {name}: {response.status} - {await response.text()}")

                # Отписываемся от снятых подписок
                for name in current_subscriptions:
                    if name not in selected:
                        subscription_id = name_to_id.get(name)
                        if subscription_id:
                            async with session.post(
                                url=f"{url_subscription}{subscription_id}/unsubscribe/",
                                headers=headers,
                                json={"tg_id": user_id}
                            ) as response:
                                if response.status != 200:
                                    print(f"Ошибка при отписке от {name}: {response.status} - {await response.text()}")

            await callback.message.answer(
                "Ваши подписки успешно обновлены!",
                reply_markup=await get_profile_inline_kb()
            )
            await state.clear()
        except Exception as e:
            print(f"Сбой при обновлении подписок: {e}")
            await callback.message.answer(
                "Произошла ошибка при обновлении подписок. Попробуйте позже.",
                reply_markup=await get_profile_inline_kb()
            )
        finally:
            await callback.answer()
        return

    # Обработка выбора/снятия подписки
    if callback.data in available_options:
        if callback.data in selected:
            selected.remove(callback.data)
        else:
            selected.append(callback.data)

        await state.update_data(selected=selected)
        new_markup = await build_interests_keyboard(selected)

        if callback.message.reply_markup != new_markup:
            await callback.message.edit_reply_markup(reply_markup=new_markup)

    await callback.answer()
    

# Хендлер для кнопки "Мои подписки"
@profile_router.callback_query(F.data == "my_bonuses")
async def my_bonuses_handler(callback: CallbackQuery):
    """
    Обрабатывает запрос пользователя на получение информации о бонусах.
    Аргументы:
        callback (CallbackQuery): Объект callback-запроса от пользователя Telegram.
    Описание:
        - Проверяет наличие карты лояльности у пользователя.
        - Если карта отсутствует, отправляет сообщение с предложением присоединиться к системе лояльности.
        - Если карта есть, делает запрос к внешнему API для получения баланса бонусов.
        - В случае успешного получения баланса отправляет пользователю сообщение с количеством бонусов.
        - В случае ошибки информирует пользователя о проблеме и записывает ошибку в лог.
    Исключения:
        Логирует и обрабатывает любые исключения, возникающие в процессе выполнения.
    """

    user_id = callback.from_user.id
    await callback.answer()

    url = f"{url_loyalty}balance/?tg_id={user_id}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}

    try:
        # Проверка наличия карты лояльности у пользователя
        card = await fetch_loyalty_card(user_id)
        if not card:
            await callback.message.answer(
                "Для получения бонусов необходимо быть участником нашей системы лояльности",
                reply_markup = await no_user_data_inline_kb()
            )
            return

        # Получаем баланс
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    balance = data.get("balance")
                else:
                    await callback.message.answer(
                        "Произошла ошибка при получении баллов. Попробуйте позже или обратитесь в поддержку.",
                        reply_markup=main_kb
                    )
                    return

        # Формируем сообщение с балансом
        bonus_word = get_bonus_word_form(balance)
        bonus_data_message = f"Ваш баланс - {balance} {bonus_word}"

        await callback.message.answer(
            bonus_data_message,
            reply_markup=await bonus_data_inline_kb()
        )

    except Exception as e:
        logger.exception(f"Ошибка при получении баланса или карты для пользователя {user_id}: {e}")
        await callback.message.answer("Произошла ошибка при получении информации о бонусах.")