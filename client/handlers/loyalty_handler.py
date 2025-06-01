import logging
import re
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp

from data.url import url_loyalty, url_users

# Регулярные выражения для валидации
name_pattern = re.compile(r"^[А-Яа-яA-Za-zёЁ\-]{2,}$")
email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$")

logger = logging.getLogger(__name__)

loyalty_router = Router()

# FSM состояния
class LoyaltyCardForm(StatesGroup):
    last_name = State()
    first_name = State()
    birth_date = State()
    email = State()

# Запрос карты
async def fetch_loyalty_card(user_id: int):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{url_loyalty}{user_id}/") as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 404:
                return None
            else:
                raise Exception(f"Ошибка получения карты: {await resp.text()}")


# Обновление данных юзера
async def update_user_data(user_id: int, first_name: str, last_name: str, birth_date: str, email: str):
    payload = {
        "user_first_name": first_name,
        "user_last_name": last_name,
        "birth_date": birth_date,
        "email": email
    }
    async with aiohttp.ClientSession() as session:
        async with session.patch(f"{url_users}{user_id}/", json=payload) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                raise Exception(f"Ошибка обновления пользователя: {await resp.text()}")


# Создание карты
async def create_loyalty_card(user_id: int):
    payload = {
        "user_id": user_id
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url_loyalty, json=payload) as resp:
            if resp.status == 201:
                return await resp.json()
            elif resp.status == 400:
                text = await resp.text()
                if "у вас уже есть карта" in text.lower():
                    return None
                else:
                    raise Exception(f"Ошибка создания карты: {text}")
            else:
                raise Exception(f"Ошибка создания карты: {await resp.text()}")


# Запуск процесса
@loyalty_router.message(F.text.lower() == "💳 карта лояльности")
async def handle_loyalty_request(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Очистка текущего состояния FSM
    await state.clear()

    # Поиск карты лояльности
    card = await fetch_loyalty_card(user_id)

    if card:
        card_image_url = card.get("card_image")
        if card_image_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(card_image_url) as img_resp:
                    if img_resp.status == 200:
                        img_bytes = await img_resp.read()
                        image = BufferedInputFile(img_bytes, filename="loyalty_card.png")
                        await message.answer_photo(photo=image)
                        return
        await message.answer("Карта найдена, но изображение недоступно.")
        return

    # Если карты нет — запускаем FSM
    await state.set_state(LoyaltyCardForm.last_name)
    await message.answer("Введите вашу фамилию:")


@loyalty_router.message(LoyaltyCardForm.last_name)
async def collect_last_name(message: Message, state: FSMContext):
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Фамилия должна содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return

    await state.update_data(last_name=message.text.strip())
    await state.set_state(LoyaltyCardForm.first_name)
    await message.answer("Введите ваше имя:")


@loyalty_router.message(LoyaltyCardForm.first_name)
async def collect_first_name(message: Message, state: FSMContext):
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Имя должно содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return

    await state.update_data(first_name=message.text.strip())
    await state.set_state(LoyaltyCardForm.birth_date)
    await message.answer("Введите дату рождения (в формате ДД.ММ.ГГГГ):")


@loyalty_router.message(LoyaltyCardForm.birth_date)
async def collect_birth_date(message: Message, state: FSMContext):
    try:
        birth_date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        birth_date_iso = birth_date_obj.date().isoformat()
    except ValueError:
        await message.answer("⚠️ Неверный формат. Попробуйте снова (ДД.ММ.ГГГГ):")
        return

    await state.update_data(birth_date=birth_date_iso)
    await state.set_state(LoyaltyCardForm.email)
    await message.answer("Введите ваш email:")


@loyalty_router.message(LoyaltyCardForm.email)
async def collect_email_and_create(message: Message, state: FSMContext):
    if not email_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Неверный формат email. Попробуйте снова:")
        return

    await state.update_data(email=message.text.strip())
    data = await state.get_data()
    user_id = message.from_user.id

    try:
        await update_user_data(
            user_id=user_id,
            first_name=data["first_name"],
            last_name=data["last_name"],
            birth_date=data["birth_date"],
            email=data["email"]
        )

        card = await create_loyalty_card(user_id)

        # Если карта уже есть — получаем её
        if card is None:
            card = await fetch_loyalty_card(user_id)

        card_image_url = card.get("card_image")
        if not card_image_url:
            await message.answer("Карта найдена, но изображение отсутствует.")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(card_image_url) as img_resp:
                if img_resp.status == 200:
                    img_bytes = await img_resp.read()
                    image = BufferedInputFile(img_bytes, filename="loyalty_card.png")
                    await message.answer_photo(
                        photo=image,
                    )
                else:
                    await message.answer("Карта найдена, но не удалось загрузить изображение.")

    except Exception as e:
        logger.exception("Ошибка при создании карты пользователя")

        error_text = str(e)
        if "DOCTYPE html" in error_text:
            short_message = "Сервер вернул HTML. Проверь консоль или логи Django!"
        elif len(error_text) > 3000:
            short_message = f"Ошибка: {error_text[:3000]}..."
        else:
            short_message = f"Ошибка: {error_text}"

        await message.answer(short_message, parse_mode=None)

    await state.clear()