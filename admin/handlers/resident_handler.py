import aiohttp
from aiogram import F, Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from admin.keyboards.admin_inline import residents_management_inline_keyboard, \
    get_categories_keyboard, get_delete_categories_keyboard, get_confirmation_keyboard
from admin.services.utils import create_new_category, fetch_categories, \
    create_category, delete_category
from data.config import config_settings
from admin.keyboards.admin_reply import admin_keyboard, residents_management_keyboard, get_back_keyboard
from data.url import url_resident, url_category
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID

import logging
logger = logging.getLogger(__name__)

admin_resident_router = Router()
admin_resident_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([ADMIN_CHAT_ID], show_message=False)
)


# =================================================================================================
# FSM
# =================================================================================================


class CategoryForm(StatesGroup):
    waiting_for_new_category = State()
    waiting_for_delete_confirmation = State()


class ResidentForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_category = State()
    waiting_for_new_category = State()
    waiting_for_address = State()
    waiting_for_floor = State()
    waiting_for_office = State()
    editing_resident = State()


# =================================================================================================
#
# =================================================================================================


@admin_resident_router.message(F.text == "🏢 Резиденты")
async def handle_residents(message: Message):
    await message.answer(
        "<b>Управление резидентами и категориями</b>",
        reply_markup=residents_management_inline_keyboard()
    )


# =================================================================================================
# Категории
# =================================================================================================


@admin_resident_router.callback_query(F.data == "resident_categories")
async def handle_categories(callback: CallbackQuery):
    """Обработчик раздела категорий"""
    await callback.message.delete()  # Удаляем предыдущее сообщение
    categories = await fetch_categories()

    if categories:
        categories_list = "\n".join([f"• {cat['name']}" for cat in categories])
        text = f"📋 Список категорий:\n{categories_list}"
    else:
        text = "📋 Список категорий пуст."

    await callback.message.answer(
        text,
        reply_markup=get_categories_keyboard()
    )
    await callback.answer()


@admin_resident_router.callback_query(F.data == "add_category")
async def handle_add_category(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления категории"""
    await callback.message.edit_text(
        "Введите название новой категории:",
        reply_markup=InlineKeyboardBuilder()
        .button(text="Отмена", callback_data="cancel_add_category")
        .as_markup()
    )
    await state.set_state("waiting_for_category_name")
    await callback.answer()


@admin_resident_router.message(F.text, StateFilter("waiting_for_category_name"))
async def process_category_name(message: Message, state: FSMContext):
    """Обработка введенного названия категории"""
    category_name = message.text.strip()

    if len(category_name) < 2:
        await message.answer("Название должно быть не короче 2 символов.")
        return

    success = await create_category(category_name)
    if success:
        await message.answer(f"Категория '{category_name}' успешно добавлена!")
    else:
        await message.answer("Ошибка при добавлении категории.")

    await state.clear()
    # Обновляем список категорий
    categories = await fetch_categories()
    text = "📋 Список категорий:\n" + "\n".join(
        [f"• {cat['name']}" for cat in categories]) if categories else "📋 Список категорий пуст."
    await message.answer(text, reply_markup=get_categories_keyboard())


@admin_resident_router.callback_query(F.data == "delete_category_menu")
async def handle_delete_category_menu(callback: CallbackQuery):
    """Обработчик меню удаления категории"""
    categories = await fetch_categories()

    if not categories:
        await callback.answer("Нет категорий для удаления", show_alert=True)
        return

    await callback.message.edit_text(
        "Выберите категорию для удаления:",
        reply_markup=get_delete_categories_keyboard(categories)
    )
    await callback.answer()


@admin_resident_router.callback_query(F.data.startswith("confirm_delete_category_"))
async def handle_confirm_delete(callback: CallbackQuery):
    """Обработчик подтверждения удаления"""
    category_id = int(callback.data.split("_")[-1])
    categories = await fetch_categories()
    category = next((cat for cat in categories if cat['id'] == category_id), None)

    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        f"Вы уверены, что хотите удалить категорию '{category['name']}'?",
        reply_markup=get_confirmation_keyboard(category_id)
    )
    await callback.answer()


@admin_resident_router.callback_query(F.data.startswith("delete_category_"))
async def handle_delete_category(callback: CallbackQuery):
    """Обработчик удаления категории"""
    category_id = int(callback.data.split("_")[-1])
    success = await delete_category(category_id)

    if success:
        await callback.message.edit_text("Категория успешно удалена!")
    else:
        await callback.message.edit_text("Ошибка при удалении категории.")

    # Возвращаемся к списку категорий
    categories = await fetch_categories()
    text = "📋 Список категорий:\n" + "\n".join(
        [f"• {cat['name']}" for cat in categories]) if categories else "📋 Список категорий пуст."
    await callback.message.answer(text, reply_markup=get_categories_keyboard())
    await callback.answer()


# Отмена действий
@admin_resident_router.callback_query(F.data == "cancel_add_category")
async def cancel_add_category(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления категории"""
    await state.clear()
    categories = await fetch_categories()
    text = "📋 Список категорий:\n" + "\n".join(
        [f"• {cat['name']}" for cat in categories]) if categories else "📋 Список категорий пуст."
    await callback.message.edit_text(text, reply_markup=get_categories_keyboard())
    await callback.answer()


@admin_resident_router.callback_query(F.data == "cancel_delete_category")
async def cancel_delete_category(callback: CallbackQuery):
    """Отмена удаления категории"""
    categories = await fetch_categories()
    text = "📋 Список категорий:\n" + "\n".join(
        [f"• {cat['name']}" for cat in categories]) if categories else "📋 Список категорий пуст."
    await callback.message.edit_text(text, reply_markup=get_categories_keyboard())
    await callback.answer()


# Возврат в меню резидентов
@admin_resident_router.callback_query(F.data == "back_to_residents_management")
async def back_to_residents_management(callback: CallbackQuery):
    """Возврат в меню управления резидентами"""
    await callback.message.edit_text(
        "Управление резидентами:",
        reply_markup=residents_management_inline_keyboard()
    )
    await callback.answer()


# Хендлер для кнопки "Назад" в инлайн-клавиатуре
@admin_resident_router.callback_query(F.data == "admin_back")
async def back_to_admin_menu_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "Возврат в главное меню",
        reply_markup=None
    )
    await callback.message.answer(
        "Главное меню администратора",
        reply_markup=admin_keyboard()
    )
    await callback.answer()


# =================================================================================================
# Добавление нового резидента
# =================================================================================================


# Хендлер кнопки "Добавить резидента"
@admin_resident_router.message(F.text == "➕ Добавить резидента")
async def add_resident_start(message: Message, state: FSMContext):
    await state.set_state(ResidentForm.waiting_for_name)
    await message.answer("Введите название резидента:",
                         reply_markup=get_back_keyboard())


# Обработка названия
@admin_resident_router.message(ResidentForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.clear()
        await message.answer(
            "Управление резидентами",
            reply_markup=residents_management_keyboard()
        )
        return

    await state.update_data(name=message.text)
    markup = await get_categories_keyboard()
    if markup:
        await state.set_state(ResidentForm.waiting_for_category)
        # Добавляем кнопку Назад к инлайн-клавиатуре
        reply_markup = InlineKeyboardMarkup(inline_keyboard=markup.inline_keyboard + [
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_name")]
        ])
        await message.answer("Выберите категорию:", reply_markup=reply_markup)
    else:
        await state.set_state(ResidentForm.waiting_for_new_category)
        await message.answer(
            "Категории отсутствуют. Введите название новой категории:",
            reply_markup=get_back_keyboard()
        )


# Обработка выбора категории
# @admin_resident_router.callback_query(F.data.startswith("category_"), ResidentForm.waiting_for_category)
# async def process_category(callback: CallbackQuery, state: FSMContext):
#     category = callback.data.split("_")[1]
#     await state.update_data(category=category)
#     await callback.message.answer("Введите описание резидента:")
#     await state.set_state(ResidentForm.waiting_for_description)
#     await callback.answer()
#
#
# # Обработка ввода новой категории
# @admin_resident_router.message(ResidentForm.waiting_for_new_category)
# async def process_new_category(message: Message, state: FSMContext):
#     category_name = message.text.strip()
#     if not category_name:
#         await message.answer("Название категории не может быть пустым. Введите ещё раз:")
#         return
#     # Создаём категорию в БД
#     category_id = await create_new_category(category_name)
#     if category_id is None:
#         await message.answer("Ошибка при создании категории. Попробуйте ещё раз:")
#         return
#     await state.update_data(category=category_id)  # Сохраняем id категории
#     await message.answer("Введите описание резидента:")
#     await state.set_state(ResidentForm.waiting_for_)
#
#
# # Обработка ввода описания
# @admin_resident_router.message(ResidentForm.waiting_for_description)
# async def process_description(message: Message, state: FSMContext):
#     description = message.text.strip()
#     if not description:
#         await message.answer("Описание не может быть пустым. Введите ещё раз:")
#         return
#
#     # Сохраняем описание в state
#     await state.update_data(description=description)
#
#     # Получаем данные из state
#     data = await state.get_data()
#     name = data.get('name')
#     category_id = data.get('category')
#
#     # Создаём резидента в БД
#     resident = await create_new_resident(name, category_id, description)
#     if resident is None:
#         await message.answer("Ошибка при создании резидента. Попробуйте ещё раз:")
#         return
#
#     # Очищаем состояние и завершаем процесс
#     await state.clear()
#     await message.answer(f"Резидент '{name}' успешно создан!")
#
#
# # =================================================================================================
# # Редактирование резидента
# # =================================================================================================
#
#
# # Хендлер кнопки "Редактировать резидента"
# @admin_resident_router.message(F.text == "✏️ Редактировать резидента")
# async def edit_resident_start(message: Message):
#     # Здесь должна быть логика получения списка резидентов из БД
#     residents = ["Resident 1", "Resident 2"]  # Замените на реальный запрос к БД
#
#     if not residents:
#         await message.answer("Нет доступных резидентов для редактирования")
#         return
#
#     builder = ReplyKeyboardBuilder()
#     for resident in residents:
#         builder.button(text=f"✏️ {resident}")
#     builder.button(text="◀️ Назад")
#     builder.adjust(1)
#
#     await message.answer(
#         "Выберите резидента для редактирования:",
#         reply_markup=builder.as_markup(resize_keyboard=True)
#     )
#
#
# # =================================================================================================
# # Удаление резидента
# # =================================================================================================
#
#
# # Хендлер кнопки "Удалить резидента"
# @admin_resident_router.message(F.text == "🗑️ Удалить резидента")
# async def delete_resident_start(message: Message):
#     # Здесь должна быть логика получения списка резидентов из БД
#     residents = ["Resident 1", "Resident 2"]  # Замените на реальный запрос к БД
#
#     if not residents:
#         await message.answer("Нет доступных резидентов для удаления")
#         return
#
#     builder = ReplyKeyboardBuilder()
#     for resident in residents:
#         builder.button(text=f"🗑️ {resident}")
#     builder.button(text="◀️ Назад")
#     builder.adjust(1)
#
#     await message.answer(
#         "Выберите резидента для удаления:",
#         reply_markup=builder.as_markup(resize_keyboard=True)
#     )
#
