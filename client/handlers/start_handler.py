import logging

import aiohttp
from aiogram import Router, types, F
from aiogram.types import Message as AiogramMessage, Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart
from aiohttp import ClientConnectorError, ServerTimeoutError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from data.config import config_settings
from data.url import url_users, url_subscription
from client.keyboards.reply import main_kb
from client.keyboards.inline import build_interests_keyboard, get_subscriptions_name
from client.services.subscriptions import get_subscriptions_data

logger = logging.getLogger(__name__)

start_router = Router()


# Пользователь выбирает интересы
class Form(StatesGroup):
    choosing = State()


async def send_new_user_notification(bot, user_data: dict, referral_code: str = None):
    """Отправляет уведомление в админ-группу о новом пользователе"""
    try:
        # Форматируем информацию о пользователе
        user_info = (
            "🎉 *Новый пользователь в боте!*\n\n"
            f"*ID:* `{user_data['tg_id']}`\n"
            f"*Имя:* {user_data['first_name'] or 'Не указано'}\n"
            f"*Фамилия:* {user_data['last_name'] or 'Не указана'}\n"
            f"*Username:* @{user_data['username'] or 'Не указан'}\n"
        )

        user_info += f"*Бот:* {'Да' if user_data['is_bot'] else 'Нет'}"

        # Отправляем сообщение в админ-группу
        await bot.send_message(
            chat_id=config_settings.ADMIN_CHAT_ID,
            text=user_info
        )
        logger.info(f"Уведомление о новом пользователе отправлено в админ-группу: {user_data['tg_id']}")

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в админ-группу: {e}")


@start_router.message(CommandStart())
async def cmd_start(message: AiogramMessage, state: FSMContext):
    """Обрабатывает команду /start для регистрации или приветствия пользователя.

    Args:
        message (Message): Сообщение с командой /start.

    Notes:
        Выполняет POST-запрос к API для регистрации и отправляет приветствие в зависимости от статуса (200 или 201).
    """
    await state.clear()
    parts = message.text.split()
    referral_code = parts[1] if len(parts) > 1 else None
    
    # Данные пользователя, отправляемые при регистрации в API
    user_data = {
        "tg_id": message.from_user.id,
        "first_name": message.from_user.first_name or "",
        "last_name": message.from_user.last_name or "",
        "username": message.from_user.username or "",
        "is_bot": message.from_user.is_bot,
        "referral_code_used": referral_code if referral_code else None
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            try:
                async with session.post(
                        url_users,
                        json=user_data,
                        headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
                ) as resp:
                    response_data = await resp.json()

                    # 201 — новый пользователь, запускаем процесс выбора интересов
                    # 200 — существующий пользователь, просто приветствуем
                    if resp.status in (200, 201):
                        greeting_name = response_data.get('first_name', message.from_user.first_name)

                        # Определяем текст приветствия
                        if resp.status == 201:
                            # Отправляем уведомление в админ-группу о новом пользователе
                            await send_new_user_notification(message.bot, user_data, referral_code)
                            # Приветственный текст
                            greeting_text = (
                                "<b>Здравствуйте!</b>\n\n"
                                "<b>Добро пожаловать в мир Арт-пространства 🎉</b>\n\n"
                                "Чтобы подсказать Вам самое интересное из жизни Арт-пространства, отметьте, что Вам ближе 💛"
                            )

                            await state.set_state(Form.choosing)
                            await state.update_data(selected=[])

                            await message.answer(
                                greeting_text,
                                reply_markup = await build_interests_keyboard([])
                            )

                        elif resp.status == 200:
                            greeting_text = "Рады снова приветствовать Вас в боте Арт-пространства ❤"

                            await message.answer(
                                f"Здравствуйте, <b>{greeting_name}</b>!\n\n"
                                f"{greeting_text}",
                                reply_markup=main_kb
                            )

                    # Обработка других статусов
                    else:
                        error_msg = response_data.get('detail', 'Сервис временно недоступен')
                        logger.error(f"API error {resp.status}: {error_msg}")
                        await message.answer(
                            f"Здравствуйте, <b>{message.from_user.first_name}</b>!\n"
                            f"⚠️ {error_msg}\n\n"
                            "Попробуйте позже или обратитесь в поддержку."
                        )

            except ServerTimeoutError:
                logger.error("Таймаут подключения к серверу")
                await message.answer(
                    f"⏳ <b>{message.from_user.first_name}</b>, сервер не отвечает.\n"
                    "Попробуйте через несколько минут."
                )

            except ClientConnectorError as e:
                logger.error(f"Ошибка подключения: {str(e)}")
                await message.answer(
                    f"🔌 <b>Технические неполадки</b>\n\n"
                    f"Здравствуйте, <b>{message.from_user.first_name}</b>!\n"
                    "Не удалось подключиться к серверу.\n\n"
                    "🛠️ Мы уже решаем проблему!\n"
                    "🕒 Попробуйте через 15-20 минут."
                )

            except Exception as e:
                logger.error(f"Ошибка запроса: {str(e)}")
                await message.answer(
                    f"🌀 <b>Неожиданная ошибка</b>\n\n"
                    f"Здравствуйте, <b>{message.from_user.first_name}</b>!\n"
                    "Произошла непредвиденная ошибка.\n\n"
                    "Наши специалисты уже в курсе и работают над решением."
                )

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        await message.answer(
            f"👋 <b>{message.from_user.first_name}</b>, добро пожаловать!\n"
            "Сервис временно ограничен, но основные функции доступны.",
            reply_markup=main_kb
        )


@start_router.callback_query(Form.choosing)
async def process_choice(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор пользователя при выборе интересов (подписок) через callback-кнопки.
    Аргументы:
        callback (types.CallbackQuery): Объект callback-запроса от пользователя.
        state (FSMContext): Контекст состояния конечного автомата для хранения данных пользователя.
    Описание:
        - Если пользователь нажал кнопку "Готово" ("done"):
            - Проверяет, выбраны ли интересы. Если нет — отправляет уведомление.
            - Получает данные о подписках и отправляет запросы на подписку для каждого выбранного интереса.
            - В случае ошибки выводит сообщение в консоль.
            - Отправляет пользователю сообщение с подтверждением и иконкой меню.
            - Очищает состояние пользователя.
        - Если пользователь выбирает или отменяет интерес:
            - Обновляет список выбранных интересов в состоянии.
            - Перестраивает клавиатуру с учетом новых выбранных интересов.
            - Обновляет разметку сообщения, если она изменилась.
        - В конце всегда отправляет ответ на callback-запрос.
    """

    data = await state.get_data()
    selected = data.get("selected", [])

    # Получаем список названий подписок из API
    available_options = await get_subscriptions_name()

    # Пользователь нажал "Готово" — отправляем данные о подписках
    if callback.data == "done":
        if not selected:
            await callback.answer("Вы ничего не выбрали!")
            return
        
        try:
            subscriptions = await get_subscriptions_data()
            # Преобразуем список подписок в словарь: {название: id}
            name_to_id = {sub["name"]: sub["id"] for sub in subscriptions}

            headers = {
                "X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()
            }

            user_id = str(callback.from_user.id)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                for name in selected:
                    subscription_id = name_to_id.get(name)
                    if not subscription_id:
                        continue

                    async with session.post(
                        url=f"{url_subscription}{subscription_id}/subscribe/",
                        headers=headers,
                        json={"tg_id": user_id}
                    ) as response:
                        if response.status != 200:
                            print(f"Ошибка при подписке на {name}: {response.status}")
        except Exception as e:
            logger.exception("Сбой при отправке подписок")

        interests_text = (
            "Супер! Мы запомнили ваши интересы. Вы всегда можете изменить их в личном кабинете. "
            "Воспользуйся командой /help, если хотите разобраться, как здесь всё устроено."
        )

        await callback.message.answer(
            text=interests_text,
            parse_mode="HTML",
            reply_markup=main_kb
        )
        await state.clear()
        return

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


@start_router.message(F.text == "/help")
async def help_command(message: AiogramMessage):
    help_text = (
    "👋 *Здравствуйте!* Я помогу Вам понять, как пользоваться ботом.\n\n"
    "*Что Вы можете сделать прямо сейчас:*\n\n"
    "▫️ */start* — *начать заново*, если что-то пошло не так.\n\n"
    "▫️ *Зайти в Личный кабинет*, где собраны ваши основные настройки:\n"
    "  ▪️ *Мои данные* — изменить информацию о себе.\n"
    "  ▪️ *Мои подписки* — посмотреть и обновить список интересов.\n"
    "  ▪️ *Мои бонусы* — узнать, сколько бонусов Вы уже накопили.\n\n"
    "▫️ *Нажать «Открыть приложение»*, чтобы попасть в Mini-App *Арт-пространства* — "
    "там Вас ждут *афиша событий*, *тематические маршруты*, *квесты* и вся информация о *наших резидентах*.\n"
    "А также ваши персональные бонусы, подарки и невероятные аватары! 🤩"
    )
    
    await message.answer(help_text, parse_mode="Markdown")

# Хендлер на реплай-кнопку "Открыть приложение"
@start_router.message(F.text == "Открыть приложение")
async def send_webapp_button(message: Message):
    webapp_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Перейти в мини-приложение",
                web_app=WebAppInfo(url="https://frontend-tau-fawn-68.vercel.app")
            )]
        ]
    )
    await message.answer(
        "Для перехода в приложение нажмите кнопку ниже.",
        reply_markup=webapp_kb
    )