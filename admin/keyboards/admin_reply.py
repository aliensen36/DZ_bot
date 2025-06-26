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
