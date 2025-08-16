import aiohttp
from aiogram import F, Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from admin.keyboards.admin_inline import residents_management_inline_keyboard, \
    get_categories_keyboard, get_delete_categories_keyboard, get_confirmation_keyboard
from admin.services.utils import fetch_categories, \
    create_category, delete_category, show_categories_message
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
    await callback.message.delete()
    await show_categories_message(callback.message.chat.id, callback.bot, get_categories_keyboard())
    await callback.answer()


@admin_resident_router.callback_query(F.data == "add_category")
async def handle_add_category(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления категории/подкатегории"""
    categories = await fetch_categories(tree=True)

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Основная категория", callback_data="add_main_category")

    if categories:
        # Собираем ID всех подкатегорий
        subcategory_ids = set()

        def collect_child_ids(cat):
            for child in cat.get('children', []):
                subcategory_ids.add(child['id'])
                collect_child_ids(child)

        for cat in categories:
            collect_child_ids(cat)

        # Добавляем только основные категории (не являющиеся подкатегориями)
        for cat in categories:
            if cat['id'] not in subcategory_ids:
                builder.button(
                    text=f"🔹 Подкатегория для: {cat['name']}",
                    callback_data=f"select_parent_{cat['id']}"
                )

    builder.button(text="❌ Отмена", callback_data="cancel_add_category")
    builder.adjust(1)

    await callback.message.edit_text(
        "Выберите тип категории:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@admin_resident_router.callback_query(F.data == "add_main_category")
async def handle_add_main_category(callback: CallbackQuery, state: FSMContext):
    """Обработчик добавления основной категории"""
    await callback.message.edit_text(
        "Введите название новой основной категории:",
        reply_markup=InlineKeyboardBuilder()
        .button(text="Отмена", callback_data="cancel_add_category")
        .as_markup()
    )
    await state.set_state("waiting_for_category_name")
    await state.update_data(parent_id=None)
    await callback.answer()


@admin_resident_router.callback_query(F.data.startswith("select_parent_"))
async def handle_select_parent(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора родительской категории"""
    parent_id = int(callback.data.split("_")[-1])
    await state.update_data(parent_id=parent_id)

    await callback.message.edit_text(
        "Введите название новой подкатегории:",
        reply_markup=InlineKeyboardBuilder()
        .button(text="Отмена", callback_data="cancel_add_category")
        .as_markup()
    )
    await state.set_state("waiting_for_category_name")
    await callback.answer()


@admin_resident_router.message(F.text, StateFilter("waiting_for_category_name"))
async def process_category_name(message: Message, state: FSMContext):
    """Обработка введенного названия категории"""
    data = await state.get_data()
    parent_id = data.get('parent_id')
    category_name = message.text.strip()

    if len(category_name) < 2:
        await message.answer("Название должно быть не короче 2 символов.")
        return

    success = await create_category(category_name, parent_id)
    if success:
        parent_text = f" (подкатегория)" if parent_id else ""
        await message.answer(f"Категория '{category_name}'{parent_text} успешно добавлена!")
    else:
        await message.answer("Ошибка при добавлении категории.")

    await state.clear()
    await show_categories_message(message.chat.id, message.bot, get_categories_keyboard())



@admin_resident_router.callback_query(F.data == "delete_category_menu")
async def handle_delete_category_menu(callback: CallbackQuery):
    """Обработчик меню удаления категории"""
    categories = await fetch_categories(tree=True)

    if not categories:
        await callback.answer("Нет категорий для удаления", show_alert=True)
        return

    builder = get_delete_categories_keyboard(categories)
    builder.button(text="↩️ Отмена", callback_data="cancel_delete_category")
    builder.adjust(1)

    await callback.message.edit_text(
        "Выберите категорию для удаления (вместе с подкатегориями):",
        reply_markup=builder.as_markup()
    )
    await callback.answer()



@admin_resident_router.callback_query(F.data.startswith("confirm_delete_category_"))
async def handle_confirm_delete(callback: CallbackQuery):
    """Обработчик подтверждения удаления"""
    category_id = int(callback.data.split("_")[-1])
    categories = await fetch_categories(tree=True)

    # Находим категорию в дереве
    def find_category(tree, cat_id):
        for cat in tree:
            if cat['id'] == cat_id:
                return cat
            found = find_category(cat.get('children', []), cat_id)
            if found:
                return found
        return None

    category = find_category(categories, category_id)

    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    # Формируем список всех удаляемых категорий (родитель + дети)
    def get_all_children(cat):
        children = [cat['name']]
        for child in cat.get('children', []):
            children.extend(get_all_children(child))
        return children

    deleting_categories = get_all_children(category)
    deleting_text = "\n".join(f"• {name}" for name in deleting_categories)

    await callback.message.edit_text(
        f"Вы уверены, что хотите удалить категорию '{category['name']}' и все её подкатегории?\n"
        f"Будут удалены:\n{deleting_text}",
        reply_markup=get_confirmation_keyboard(category_id)
    )
    await callback.answer()


@admin_resident_router.callback_query(F.data.startswith("delete_category_"))
async def handle_delete_category(callback: CallbackQuery):
    """Обработчик удаления категории"""
    category_id = int(callback.data.split("_")[-1])
    success = await delete_category(category_id)

    if success:
        await callback.message.edit_text("Категория и все подкатегории успешно удалены!")
    else:
        await callback.message.edit_text("Ошибка при удалении категории.")

    await show_categories_message(callback.message.chat.id, callback.bot, get_categories_keyboard())
    await callback.answer()



# Отмена действий
@admin_resident_router.callback_query(F.data == "cancel_add_category")
async def cancel_add_category(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления категории"""
    await state.clear()
    await show_categories_message(callback.message.chat.id, callback.bot, get_categories_keyboard())
    await callback.answer()


@admin_resident_router.callback_query(F.data == "cancel_delete_category")
async def cancel_delete_category(callback: CallbackQuery):
    """Отмена удаления категории"""
    await show_categories_message(callback.message.chat.id, callback.bot, get_categories_keyboard())
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


