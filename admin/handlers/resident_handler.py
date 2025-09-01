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
    delete_resident_api, generate_residents_excel, fetch_category_name, fetch_resident_data
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


class EditResidentForm(StatesGroup):
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


FIELD_TRANSLATIONS = {
    "name": "Название",
    "category": "Категория",
    "address": "Адрес",
    "building": "Строение",
    "entrance": "Вход",
    "floor": "Этаж",
    "office": "Офис"
}


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


# Для подтверждения изменений полей
@admin_resident_router.message(StateFilter("*"))
async def handle_resident_field_input(message: Message, state: FSMContext):
    current_state = await state.get_state()

    # Проверяем, находимся ли мы в процессе редактирования (есть данные в state)
    data = await state.get_data()
    field_code = data.get("edit_field")
    resident_id = data.get("resident_id")

    if field_code and resident_id:
        # Получаем русское название поля
        field_name = FIELD_TRANSLATIONS.get(field_code, field_code)
        new_value = message.text

        # Получаем текущие данные резидента
        resident_data, error = await fetch_resident_data(resident_id)
        if error:
            await message.answer(error)
            await state.clear()
            return

        # Получаем старое значение
        old_value = resident_data.get(field_code, "Не указано")
        if old_value is None:
            old_value = "Не указано"

        # Сохраняем данные для подтверждения
        await state.update_data(
            field_code=field_code,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            resident_name=resident_data.get('name', 'Неизвестный резидент')
        )

        # Показываем подтверждение
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"confirm_field_update_{field_code}"
            ),
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"back_to_edit_{resident_id}"
            )
        )

        await message.answer(
            f"📋 <b>Подтверждение изменения</b>\n\n"
            f"🏢 <b>Резидент:</b> {resident_data.get('name', 'Неизвестный')}\n"
            f"📝 <b>Поле:</b> {field_name}\n"
            f"📄 <b>Текущее значение:</b> {old_value}\n"
            f"🆕 <b>Новое значение:</b> {new_value}\n\n"
            f"Вы уверены, что хотите изменить?",
            reply_markup=builder.as_markup()
        )
    else:
        # Если не в состоянии редактирования, игнорируем сообщение
        # Это предотвратит реакцию на "ок" и другие сообщения
        pass


async def show_category_selection(callback: CallbackQuery, state: FSMContext, resident_id: str):
    """Показывает выбор категории с предварительной загрузкой текущей категории"""
    try:
        data = await state.get_data()

        # Получаем текущие данные резидента
        resident_data, error = await fetch_resident_data(resident_id)
        if error:
            await callback.message.edit_text(error)
            return

        current_category_id = None
        current_category_name = "Не указана"

        # Получаем категории из массива объектов
        if resident_data.get('categories') and len(resident_data['categories']) > 0:
            current_category_id = resident_data['categories'][0]['id']
            current_category_name = resident_data['categories'][0]['name']

        categories = await fetch_categories(tree=True)

        if isinstance(categories, dict) and "error" in categories:
            await callback.message.edit_text(f"❌ {categories['error']}")
            return

        builder = InlineKeyboardBuilder()

        def build_category_buttons(categories_list, level=0):
            for category in categories_list:
                indent = "    " * level
                # Добавляем отметку для текущей категории
                is_current = category['id'] == current_category_id
                current_marker = " ✅" if is_current else ""

                builder.add(InlineKeyboardButton(
                    text=f"{indent}📌 {category['name']}{current_marker}",
                    callback_data=f"update_category_{category['id']}"
                ))
                if category.get('children'):
                    build_category_buttons(category['children'], level + 1)

        build_category_buttons(categories)

        builder.row(InlineKeyboardButton(
            text="◀️ Отмена",
            callback_data=f"back_to_edit_{resident_id}"
        ))

        await callback.message.edit_text(
            f"📋 <b>Выбор новой категории</b>\n\n"
            f"🏢 <b>Резидент:</b> {resident_data.get('name', 'Неизвестный')}\n"
            f"📁 <b>Текущая категория:</b> {current_category_name}\n\n"
            f"Выберите новую категорию:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")


# Обработка редактирования полей
@admin_resident_router.callback_query(F.data.startswith("edit_field_"))
async def edit_resident_field(callback: CallbackQuery, state: FSMContext):
    field_code = callback.data.split("_")[-1]
    await state.update_data(edit_field=field_code)

    data = await state.get_data()
    resident_id = data.get('resident_id')

    # Получаем русское название поля из словаря
    field_name = FIELD_TRANSLATIONS.get(field_code, field_code)

    if field_code == "category":
        await show_category_selection(callback, state, resident_id)
    else:
        # Получаем текущее значение поля
        resident_data, error = await fetch_resident_data(resident_id)
        if error:
            await callback.message.edit_text(error)
            return

        current_value = resident_data.get(field_code, "Не указано")
        if current_value is None:
            current_value = "Не указано"

        builder = InlineKeyboardBuilder()
        builder.button(
            text="◀️ Отмена",
            callback_data=f"back_to_edit_{resident_id}"
        )

        await callback.message.edit_text(
            f"✏️ <b>Редактирование {field_name}</b>\n\n"
            f"🏢 <b>Резидент:</b> {resident_data.get('name', 'Неизвестный')}\n"
            f"📄 <b>Текущее значение:</b> {current_value}\n\n"
            f"Введите новое значение для поля {field_name}:",
            reply_markup=builder.as_markup()
        )


@admin_resident_router.callback_query(F.data.startswith("update_category_"))
async def update_resident_category(callback: CallbackQuery, state: FSMContext):
    new_category_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    resident_id = data['resident_id']

    # Получаем данные резидента
    resident_data, error = await fetch_resident_data(resident_id)
    if error:
        await callback.message.edit_text(error)
        return

    old_category_name = "Не указана"

    # Получаем категории из массива объектов
    if resident_data.get('categories') and len(resident_data['categories']) > 0:
        old_category_name = resident_data['categories'][0]['name']

    new_category_name = await fetch_category_name(new_category_id)

    # Сохраняем данные для подтверждения
    await state.update_data(
        new_category_id=new_category_id,
        old_category_name=old_category_name,
        new_category_name=new_category_name,
        resident_name=resident_data.get('name', 'Неизвестный резидент')
    )

    # Показываем подтверждение
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"confirm_category_update_{new_category_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"back_to_edit_{resident_id}"
        )
    )

    await callback.message.edit_text(
        f"📋 <b>Подтверждение изменения категории</b>\n\n"
        f"🏢 <b>Резидент:</b> {resident_data.get('name', 'Неизвестный')}\n"
        f"📁 <b>Текущая категория:</b> {old_category_name}\n"
        f"🆕 <b>Новая категория:</b> {new_category_name}\n\n"
        f"Вы уверены, что хотите изменить категорию?",
        reply_markup=builder.as_markup()
    )


@admin_resident_router.callback_query(F.data.startswith("confirm_category_update_"))
async def confirm_category_update(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    resident_id = data['resident_id']
    new_category_id = data['new_category_id']

    # Выполняем обновление
    success, message = await update_resident_category_api(
        resident_id=resident_id,
        category_id=new_category_id
    )

    if success:
        # Показываем результат с деталями
        await callback.message.edit_text(
            f"✅ <b>Категория успешно обновлена!</b>\n\n"
            f"🏢 <b>Резидент:</b> {data['resident_name']}\n"
            f"📁 <b>Было:</b> {data['old_category_name']}\n"
            f"🆕 <b>Стало:</b> {data['new_category_name']}\n\n"
            f"Вы можете продолжить редактирование или вернуться назад."
        )

        # Добавляем кнопки для продолжения
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✏️ Продолжить редактирование",
                callback_data=f"back_to_edit_{resident_id}"
            ),
            InlineKeyboardButton(
                text="◀️ Назад к списку",
                callback_data="edit_resident_list"
            )
        )
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(message)

    await state.clear()


# Обработчик подтверждения для полей
@admin_resident_router.callback_query(F.data.startswith("confirm_field_update_"))
async def confirm_field_update(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    resident_id = data['resident_id']
    field_code = data['field_code']
    new_value = data['new_value']

    # Обработка числовых полей
    if field_code in ["floor", "office"]:
        try:
            new_value = int(new_value)
        except ValueError:
            await callback.message.edit_text(
                f"❌ Некорректное значение для {data['field_name']}! Введите число."
            )
            await state.clear()
            return

    # Выполняем обновление
    success, result_message, field_name_ru = await update_resident_field_api(
        resident_id=resident_id,
        field=field_code,
        value=new_value,
        headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    )

    if success:
        # Показываем результат с деталями
        await callback.message.edit_text(
            f"✅ <b>{field_name_ru} успешно обновлено!</b>\n\n"
            f"🏢 <b>Резидент:</b> {data['resident_name']}\n"
            f"📝 <b>Поле:</b> {field_name_ru}\n"
            f"📄 <b>Было:</b> {data['old_value']}\n"
            f"🆕 <b>Стало:</b> {data['new_value']}\n\n"
            f"Вы можете продолжить редактирование или вернуться назад."
        )

        # Добавляем кнопки для продолжения
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✏️ Продолжить редактирование",
                callback_data=f"back_to_edit_{resident_id}"
            ),
            InlineKeyboardButton(
                text="◀️ Назад к списку",
                callback_data="edit_resident_list"
            )
        )
        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(result_message)

    await state.clear()


# Для кнопки "Назад" из подтверждения
@admin_resident_router.callback_query(F.data.startswith("back_to_edit_"))
async def back_to_edit_resident(callback: CallbackQuery, state: FSMContext):
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


# =================================================================================================
# Удаление резидента
# =================================================================================================

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

    # Получаем информацию о резиденте для отображения названия
    residents, error = await fetch_residents_for_deletion()
    if error:
        await callback.message.edit_text(error)
        return

    # Находим резидента по ID
    resident_to_delete = None
    for resident in residents:
        if str(resident['id']) == resident_id:
            resident_to_delete = resident
            break

    if not resident_to_delete:
        await callback.message.edit_text("❌ Резидент не найден")
        return

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
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы уверены, что хотите удалить резидента:\n"
        f"<b>🏢 {resident_to_delete['name']}</b>\n\n"
        f"Это действие нельзя отменить!",
        reply_markup=builder.as_markup()
    )


# Удаление резидента
@admin_resident_router.callback_query(F.data.startswith("delete_resident_"))
async def delete_resident(callback: CallbackQuery):
    resident_id = callback.data.split("_")[-1]

    # Сначала получаем информацию о резиденте для финального сообщения
    residents, error = await fetch_residents_for_deletion()
    if error:
        await callback.message.edit_text(error)
        return

    # Находим резидента по ID
    resident_name = "Неизвестный резидент"
    for resident in residents:
        if str(resident['id']) == resident_id:
            resident_name = resident['name']
            break

    # Выполняем удаление
    success, message = await delete_resident_api(resident_id)

    if success:
        await callback.message.edit_text(
            f"✅ <b>Резидент успешно удален</b>\n\n"
            f"🏢 <b>Удаленный резидент:</b> {resident_name}\n\n"
            f"Резидент был полностью удален из системы.",
            reply_markup=InlineKeyboardBuilder()
            .button(text="◀️ Назад к списку", callback_data="delete_resident_list")
            .as_markup()
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при удалении</b>\n\n"
            f"Не удалось удалить резидента {resident_name}:\n"
            f"{message}",
            reply_markup=InlineKeyboardBuilder()
            .button(text="◀️ Назад", callback_data="delete_resident_list")
            .as_markup()
        )
