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
    builder.button(text="Изменить название")
    builder.button(text="Изменить фото")
    builder.button(text="Изменить описание")
    builder.button(text="Изменить информацию")
    builder.button(text="Изменить дату начала")
    builder.button(text="Изменить дату окончания")
    builder.button(text="Изменить локацию")
    builder.button(text="Изменить ссылку")
    builder.button(text="Отмена")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)