import aiohttp
from aiogram import F, Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, \
    BufferedInputFile
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from admin.keyboards.admin_inline import residents_management_inline_keyboard, \
    get_categories_keyboard, get_delete_categories_keyboard, get_confirmation_keyboard, \
    get_residents_management_keyboard
from admin.services.utils import fetch_categories, \
    create_category, delete_category, show_categories_message, fetch_categories_with_keyboard, create_resident_api, \
    fetch_residents_list, update_resident_category_api, update_resident_field_api, fetch_residents_for_deletion, \
    delete_resident_api, generate_residents_excel
from data.config import config_settings
from admin.keyboards.admin_reply import admin_keyboard, residents_management_keyboard, get_back_keyboard
from data.url import url_resident, url_category
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID
from admin.handlers.points_system_settings import EditPointsSystemSettingsStates

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
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_address = State()
    waiting_for_building = State()
    waiting_for_entrance = State()
    waiting_for_floor = State()
    waiting_for_office = State()
    waiting_for_confirmation = State()


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
# Резиденты
# =================================================================================================


@admin_resident_router.callback_query(F.data == "residents_list")
async def residents_list(callback: CallbackQuery):
    await callback.message.edit_text(
        "Управление резидентами",
        reply_markup=get_residents_management_keyboard()
    )


# =================================================================================================
# Список резидентов
# =================================================================================================


@admin_resident_router.callback_query(F.data == "show_residents_list")
async def show_residents_list(callback: CallbackQuery):
    residents, error = await fetch_residents_list()

    if error:
        # Проверяем, нужно ли редактировать сообщение или отправить новое
        if callback.message.text != f"❌ {error}":
            await callback.message.edit_text(
                f"❌ {error}",
                reply_markup=get_residents_management_keyboard()
            )
        return

    if not residents:
        if callback.message.text != "Список резидентов пуст":
            await callback.message.edit_text(
                "Список резидентов пуст",
                reply_markup=get_residents_management_keyboard()
            )
        return

    # Формируем список
    new_text = "📋 Список резидентов:\n\n" + "\n".join(
        f"{idx}. {r['name']}" for idx, r in enumerate(residents, 1)
    )

    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📊 Выгрузить в Excel",
            callback_data="export_residents_to_excel"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_residents_management"
        )
    )
    new_markup = builder.as_markup()

    # Проверяем, изменились ли текст или клавиатура
    if (callback.message.text != new_text or
            str(callback.message.reply_markup) != str(new_markup)):
        await callback.message.edit_text(
            new_text,
            reply_markup=new_markup
        )


@admin_resident_router.callback_query(F.data == "export_residents_to_excel")
async def export_residents_to_excel(callback: CallbackQuery):
    excel_file, error = await generate_residents_excel()

    if error:
        if callback.message.text != f"❌ {error}":
            await callback.message.answer(
                f"❌ {error}",
                reply_markup=get_residents_management_keyboard()
            )
        await callback.answer()
        return

    try:
        await callback.answer()
        # Сбрасываем указатель файла
        excel_file.seek(0)
        # Отправляем файл
        await callback.message.answer_document(
            document=BufferedInputFile(
                excel_file.read(),
                filename="residents.xlsx"
            ),
            caption="Полный список резидентов"
        )

        # Отправляем отдельное сообщение с кнопкой "Назад"
        await callback.message.answer(
            "Вернуться к управлению резидентами",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="back_to_residents_management"
                    )]
                ]
            )
        )

    except Exception as e:
        await callback.message.answer(
            f"❌ Ошибка при отправке файла: {str(e)}",
            reply_markup=get_residents_management_keyboard()
        )
        await callback.answer()


# =================================================================================================
# Добавление резидента
# =================================================================================================


# Добавление резидента - выбор категории
@admin_resident_router.callback_query(F.data == "add_resident")
async def add_resident_start(callback: CallbackQuery, state: FSMContext):
    try:
        categories, keyboard = await fetch_categories_with_keyboard()
        await callback.message.edit_text(
            "Выберите категорию для резидента:",
            reply_markup=keyboard
        )
        await state.set_state(ResidentForm.waiting_for_category)
    except Exception as e:
        await callback.message.edit_text(f"❌ {str(e)}")


@admin_resident_router.callback_query(F.data.startswith("select_category_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем ID категории из callback_data
        category_id = callback.data.split("_")[-1]

        # Получаем название категории из текста кнопки
        for row in callback.message.reply_markup.inline_keyboard:
            for button in row:
                if button.callback_data == callback.data:
                    category_name = button.text
                    break

        if not category_name:
            raise ValueError("Не удалось найти название категории")

        await state.update_data(category_id=category_id, category_name=category_name)
        await state.set_state(ResidentForm.waiting_for_name)
        await callback.message.edit_text(
            "Введите название резидента:",
            reply_markup=InlineKeyboardBuilder().button(text="◀️ Отмена", callback_data="add_resident").as_markup()
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при выборе категории: {str(e)}")
        await callback.answer()


@admin_resident_router.message(ResidentForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ResidentForm.waiting_for_address)

    # Создаем клавиатуру с кнопкой принятия адреса по умолчанию
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Адрес по умолчанию",
            callback_data="use_default_address"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Отмена",
            callback_data="residents_list"
        )
    )

    await message.answer(
        "Введите адрес или нажмите кнопку для использования адреса по умолчанию:\n"
        "(По умолчанию: 'ул. Большая Новодмитровская, д. 36')",
        reply_markup=builder.as_markup()
    )


@admin_resident_router.callback_query(F.data == "use_default_address", ResidentForm.waiting_for_address)
async def use_default_address(callback: CallbackQuery, state: FSMContext):
    default_address = "ул. Большая Новодмитровская, д. 36"
    await state.update_data(address=default_address)
    await callback.message.edit_text(
        f"✅ Использован адрес по умолчанию: {default_address}"
    )
    await state.set_state(ResidentForm.waiting_for_building)
    await callback.message.answer(
        "Введите номер строения:",
        reply_markup=InlineKeyboardBuilder().button(
            text="◀️ Отмена",
            callback_data="residents_list"
        ).as_markup()
    )


@admin_resident_router.message(ResidentForm.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    # Если пользователь ввел текст (не нажал кнопку)
    address = message.text if message.text.strip() else "ул. Большая Новодмитровская, д. 36"
    await state.update_data(address=address)
    await state.set_state(ResidentForm.waiting_for_building)
    await message.answer(
        "Введите номер строения:",
        reply_markup=InlineKeyboardBuilder().button(
            text="◀️ Отмена",
            callback_data="residents_list"
        ).as_markup()
    )


@admin_resident_router.message(ResidentForm.waiting_for_building)
async def process_building(message: Message, state: FSMContext):
    await state.update_data(building=message.text)
    await state.set_state(ResidentForm.waiting_for_entrance)
    await message.answer(
        "Введите номер входа (если есть, или '-' чтобы пропустить):",
        reply_markup=InlineKeyboardBuilder().button(text="◀️ Отмена", callback_data="residents_list").as_markup()
    )


@admin_resident_router.message(ResidentForm.waiting_for_entrance)
async def process_entrance(message: Message, state: FSMContext):
    entrance = message.text if message.text != "-" else None
    await state.update_data(entrance=entrance)
    await state.set_state(ResidentForm.waiting_for_floor)
    await message.answer(
        "Введите номер этажа:",
        reply_markup=InlineKeyboardBuilder().button(text="◀️ Отмена", callback_data="residents_list").as_markup()
    )


@admin_resident_router.message(ResidentForm.waiting_for_floor)
async def process_floor(message: Message, state: FSMContext):
    floor = message.text.strip()
    if not floor:
        await message.answer("Номер этажа не может быть пустым")
        return

    await state.update_data(floor=floor)
    await state.set_state(ResidentForm.waiting_for_office)
    await message.answer(
        "Введите номер офиса:",
        reply_markup=InlineKeyboardBuilder().button(text="◀️ Отмена", callback_data="residents_list").as_markup()
    )


@admin_resident_router.message(ResidentForm.waiting_for_office)
async def process_office(message: Message, state: FSMContext):
    office = message.text.strip()
    if not office:
        await message.answer("Номер офиса не может быть пустым")
        return

    data = await state.get_data()

    # Формируем данные резидента
    resident_data = {
        "name": data["name"],
        "address": data["address"],
        "building": data["building"],
        "entrance": data.get("entrance"),
        "floor": data["floor"],
        "office": office,
        "category_ids": [data["category_id"]]
    }

    # Формируем сообщение с данными
    summary_message = (
        "📝 Проверьте данные нового резидента:\n\n"
        f"🏢 Наименование: {data['name']}\n"
        f"📍 Адрес: {data['address']}\n"
        f"🏗 Строение: {data['building']}\n"
        f"🚪 Вход: {data.get('entrance', 'не указан')}\n"
        f"🛗 Этаж: {data['floor']}\n"
        f"🚪 Офис: {office}\n"
        f"🏷 Категория: {data['category_name']}\n\n"
        "Подтвердите создание:"
    )

    # Создаем клавиатуру с кнопками подтверждения
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Подтвердить", callback_data="confirm_create_resident")
    keyboard.button(text="❌ Отменить", callback_data="cancel_resident_creation")

    # Сохраняем данные в state для использования при подтверждении
    await state.update_data(resident_data=resident_data)

    # Отправляем сообщение с данными и кнопками
    await message.answer(
        summary_message,
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(ResidentForm.waiting_for_confirmation)



# Обработчик подтверждения создания
@admin_resident_router.callback_query(F.data == "confirm_create_resident", ResidentForm.waiting_for_confirmation)
async def confirm_create_resident(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    resident_data = data["resident_data"]

    success, result_message = await create_resident_api(resident_data)
    await callback.message.answer(result_message)

    if success:
        await state.clear()
    await callback.answer()


# Обработчик отмены создания
@admin_resident_router.callback_query(F.data == "cancel_resident_creation", ResidentForm.waiting_for_confirmation)
async def cancel_resident_creation(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("❌ Создание резидента отменено")
    await state.clear()
    await callback.answer()


# =================================================================================================
# Редактирование резидента
# =================================================================================================


# Редактирование резидента - список
@admin_resident_router.callback_query(F.data == "edit_resident_list")
async def edit_resident_list(callback: CallbackQuery):
    residents, error = await fetch_residents_list()

    if error:
        await callback.message.edit_text(error)
        return

    builder = InlineKeyboardBuilder()
    for resident in residents:
        builder.row(InlineKeyboardButton(
            text=resident["name"],
            callback_data=f"edit_resident_{resident['id']}"
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="residents_list"
    ))

    await callback.message.edit_text(
        "Выберите резидента для редактирования:",
        reply_markup=builder.as_markup()
    )

# Редактирование резидента - выбор поля
@admin_resident_router.callback_query(F.data.startswith("edit_resident_"))
async def edit_resident_select_field(callback: CallbackQuery, state: FSMContext):
    resident_id = callback.data.split("_")[-1]
    await state.update_data(resident_id=resident_id)

    builder = InlineKeyboardBuilder()
    fields = [
        ("Название", "name"),
        ("Категория", "category"),
        ("Адрес", "address"),
        ("Строение", "building"),
        ("Вход", "entrance"),
        ("Этаж", "floor"),
        ("Офис", "office")
    ]

    for field in fields:
        builder.row(InlineKeyboardButton(
            text=f"✏️ {field[0]}",
            callback_data=f"edit_field_{field[1]}"
        ))

    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="edit_resident_list"
    ))

    await callback.message.edit_text(
        "Выберите поле для редактирования:",
        reply_markup=builder.as_markup()
    )


async def edit_resident_category(callback: CallbackQuery, state: FSMContext):
    """Отображает иерархию категорий для выбора"""
    try:
        # Получаем категории через API
        categories_response = await fetch_categories(tree=True)

        if "error" in categories_response:
            await callback.message.edit_text(f"❌ {categories_response['error']}")
            return

        # Строим иерархическую клавиатуру
        builder = InlineKeyboardBuilder()

        def build_category_buttons(categories, level=0):
            for category in categories:
                indent = "    " * level
                builder.add(InlineKeyboardButton(
                    text=f"{indent}📌 {category['name']}",
                    callback_data=f"update_category_{category['id']}"
                ))
                if category.get('children'):
                    build_category_buttons(category['children'], level + 1)

        build_category_buttons(categories_response)

        # Добавляем кнопку отмены
        builder.row(InlineKeyboardButton(
            text="◀️ Отмена",
            callback_data=lambda: edit_resident_select_field(callback, state)
        ))

        # Отправляем сообщение с клавиатурой
        await callback.message.edit_text(
            "Выберите новую категорию:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
# Обработка редактирования полей
@admin_resident_router.callback_query(F.data.startswith("edit_field_"))
async def edit_resident_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split("_")[-1]
    await state.update_data(edit_field=field)

    if field == "category":
        await edit_resident_category(callback, state)
    else:
        await callback.message.edit_text(
            f"Введите новое значение для поля {field}:",
            reply_markup=InlineKeyboardBuilder().button(
                text="◀️ Отмена",
                callback_data=lambda: edit_resident_select_field(callback, state)
            ).as_markup()
        )


@admin_resident_router.callback_query(F.data.startswith("update_category_"))
async def update_resident_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[-1])
    data = await state.get_data()

    success, message = await update_resident_category_api(
        resident_id=data['resident_id'],
        category_id=category_id
    )

    await callback.message.edit_text(message)
    await state.clear()

    if success:
        await edit_resident_list(callback)


@admin_resident_router.message()
async def update_resident_field(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("edit_field")
    resident_id = data.get("resident_id")
    
    if not field or not resident_id:
        await message.answer("❌ Ошибка: не найдены данные для обновления")
        await state.clear()
        return

    # Обработка числовых полей
    if field in ["floor", "office"]:
        try:
            value = int(message.text)
        except ValueError:
            await message.answer(f"❌ Некорректное значение для {field}! Введите число.")
            return
    else:
        value = message.text

    # Вызов API функции
    success, result_message = await update_resident_field_api(
        resident_id=resident_id,
        field=field,
        value=value,
        headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    )

    await message.answer(result_message)
    await state.clear()

    if success:
        await edit_resident_list(message)

# Удаление резидента - список
@admin_resident_router.callback_query(F.data == "delete_resident_list")
async def delete_resident_list(callback: CallbackQuery):
    residents, error = await fetch_residents_for_deletion()

    if error:
        await callback.message.edit_text(error)
        return

    builder = InlineKeyboardBuilder()
    for resident in residents:
        builder.row(InlineKeyboardButton(
            text=resident["name"],
            callback_data=f"confirm_delete_{resident['id']}"
        ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="residents_list"
    ))

    await callback.message.edit_text(
        "Выберите резидента для удаления:",
        reply_markup=builder.as_markup()
    )

# Подтверждение удаления
@admin_resident_router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_resident(callback: CallbackQuery):
    resident_id = callback.data.split("_")[-1]
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"delete_resident_{resident_id}"
        ),
        InlineKeyboardButton(
            text="❌ Нет, отмена",
            callback_data="delete_resident_list"
        )
    )
    await callback.message.edit_text(
        "Вы уверены, что хотите удалить этого резидента?",
        reply_markup=builder.as_markup()
    )


# Удаление резидента
@admin_resident_router.callback_query(F.data.startswith("delete_resident_"))
async def delete_resident(callback: CallbackQuery):
    resident_id = callback.data.split("_")[-1]
    success, message = await delete_resident_api(resident_id)

    await callback.message.edit_text(message)

    if success:
        await residents_list(callback)