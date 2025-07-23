import aiohttp
from aiogram import F, Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from admin.keyboards.admin_inline import get_categories_keyboard
from data.config import config_settings
from admin.keyboards.admin_reply import admin_keyboard, residents_management_keyboard
from data.url import url_resident, url_category
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID


admin_resident_router = Router()
admin_resident_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([ADMIN_CHAT_ID], show_message=False)
)

# Состояния для FSM
class ResidentForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_category = State()
    waiting_for_new_category = State()
    waiting_for_description = State()
    waiting_for_working_time = State()
    waiting_for_email = State()
    waiting_for_phone = State()
    waiting_for_website = State()
    waiting_for_address = State()
    waiting_for_floor = State()
    waiting_for_office = State()
    editing_resident = State()


# =================================================================================================
# Функции для работы с БД
# =================================================================================================



# =================================================================================================
# Хендлеры
# =================================================================================================

# Хендлер кнопки "Резиденты"
@admin_resident_router.message(F.text == "🏢 Резиденты")
async def handle_residents(message: Message):
    await message.answer(
        "Управление резидентами:",
        reply_markup=residents_management_keyboard()
    )


# =================================================================================================
# Добавление нового резидента
# =================================================================================================


# Хендлер кнопки "Добавить резидента"
@admin_resident_router.message(F.text == "➕ Добавить резидента")
async def add_resident_start(message: Message, state: FSMContext):
    await state.set_state(ResidentForm.waiting_for_name)
    await message.answer("Введите название резидента:", reply_markup=ReplyKeyboardRemove())


# Обработка названия
@admin_resident_router.message(ResidentForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    markup = await get_categories_keyboard()
    if markup:
        await state.set_state(ResidentForm.waiting_for_category)
        await message.answer("Выберите категорию:", reply_markup=markup)
    else:
        await state.set_state(ResidentForm.waiting_for_new_category)
        await message.answer("Категории отсутствуют. Введите название новой категории:")


# Обработка выбора категории
@admin_resident_router.callback_query(F.data.startswith("category_"), ResidentForm.waiting_for_category)
async def process_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    await callback.message.answer("Введите описание резидента:")
    await state.set_state(ResidentForm.waiting_for_description)
    await callback.answer()


# Обработка ввода новой категории
@admin_resident_router.message(ResidentForm.waiting_for_new_category)
async def process_new_category(message: Message, state: FSMContext):
    category_name = message.text.strip()
    if not category_name:
        await message.answer("Название категории не может быть пустым. Введите ещё раз:")
        return
    # Создаём категорию в БД
    category_id = await create_new_category(category_name)
    if category_id is None:
        await message.answer("Ошибка при создании категории. Попробуйте ещё раз:")
        return
    await state.update_data(category=category_id)  # Сохраняем id категории
    await message.answer("Введите описание резидента:")
    await state.set_state(ResidentForm.waiting_for_description)


# Обработка ввода описания
@admin_resident_router.message(ResidentForm.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if not description:
        await message.answer("Описание не может быть пустым. Введите ещё раз:")
        return

    # Сохраняем описание в state
    await state.update_data(description=description)

    # Получаем данные из state
    data = await state.get_data()
    name = data.get('name')
    category_id = data.get('category')

    # Создаём резидента в БД
    resident = await create_new_resident(name, category_id, description)
    if resident is None:
        await message.answer("Ошибка при создании резидента. Попробуйте ещё раз:")
        return

    # Очищаем состояние и завершаем процесс
    await state.clear()
    await message.answer(f"Резидент '{name}' успешно создан!")


# =================================================================================================
# Редактирование резидента
# =================================================================================================


# Хендлер кнопки "Редактировать резидента"
@admin_resident_router.message(F.text == "✏️ Редактировать резидента")
async def edit_resident_start(message: Message):
    # Здесь должна быть логика получения списка резидентов из БД
    residents = ["Resident 1", "Resident 2"]  # Замените на реальный запрос к БД

    if not residents:
        await message.answer("Нет доступных резидентов для редактирования")
        return

    builder = ReplyKeyboardBuilder()
    for resident in residents:
        builder.button(text=f"✏️ {resident}")
    builder.button(text="◀️ Назад")
    builder.adjust(1)

    await message.answer(
        "Выберите резидента для редактирования:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


# =================================================================================================
# Удаление резидента
# =================================================================================================


# Хендлер кнопки "Удалить резидента"
@admin_resident_router.message(F.text == "🗑️ Удалить резидента")
async def delete_resident_start(message: Message):
    # Здесь должна быть логика получения списка резидентов из БД
    residents = ["Resident 1", "Resident 2"]  # Замените на реальный запрос к БД

    if not residents:
        await message.answer("Нет доступных резидентов для удаления")
        return

    builder = ReplyKeyboardBuilder()
    for resident in residents:
        builder.button(text=f"🗑️ {resident}")
    builder.button(text="◀️ Назад")
    builder.adjust(1)

    await message.answer(
        "Выберите резидента для удаления:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


# =================================================================================================
# Кнопка "Нахад"
# =================================================================================================

# Хендлер кнопки "Назад"
@admin_resident_router.message(F.text == "◀️ Назад")
async def back_to_admin_menu(message: Message):
    await message.answer(
        "Возврат в главное меню",
        reply_markup=admin_keyboard()
    )
