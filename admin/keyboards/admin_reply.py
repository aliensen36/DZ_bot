from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def admin_keyboard():
    """Создаёт reply-клавиатуру для админ-панели.

    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопками "Статистика", "Рассылка", "Выход".

    Notes:
        Клавиатура отображается в два столбца.
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text="📊 Статистика")
    builder.button(text="📢 Рассылка")
    builder.button(text="🏢 Резиденты")
    builder.button(text="🎉 Мероприятия")
    builder.button(text="🔧 Настройки бонусной системы")
    # builder.button(text="🔧 Настройки")
    builder.button(text="Выход")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# Клавиатура управления резидентами
def residents_management_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Добавить резидента")
    builder.button(text="✏️ Редактировать резидента")
    builder.button(text="🗑️ Удалить резидента")
    builder.button(text="◀️ Назад")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# Клавиатура с кнопкой "Назад"
def get_back_keyboard():
    """Возвращает клавиатуру только с кнопкой Назад"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="◀️ Назад")]],
        resize_keyboard=True
    )
    return keyboard


# Клавиатура управления мероприятиями
def events_management_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Добавить мероприятие")
    builder.button(text="Редактировать мероприятие")
    builder.button(text="Удалить мероприятие")
    builder.button(text="Назад")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Клавиатура для отмены
def cancel_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Отмена")
    return builder.as_markup(resize_keyboard=True)

# Клавиатура для редактирования мероприятия
def edit_event_keyboard():
    builder = ReplyKeyboardBuilder()
    buttons = [
        "Изменить название",
        "Изменить фото",
        "Изменить описание",
        "Изменить информацию",
        "Изменить дату начала",
        "Изменить дату окончания",
        "Изменить доступность регистрации",
        "Изменить ссылку на регистрацию",
        "Изменить доступность билетов",
        "Изменить ссылку на покупку билета",
        "Изменить локацию",
        "Отмена"
    ]
    for text in buttons:
        builder.button(text=text)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Клавиатура для управления настройками бонусной системы
def points_system_settings_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Изменить настройки")
    builder.button(text="Назад")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

# Клавиатура для редактирования настроек бонусной системы
def edit_points_system_settings_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Изменить баллы за 100 рублей")
    builder.button(text="Изменить баллы за 1% скидки")
    builder.button(text="Назад")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)