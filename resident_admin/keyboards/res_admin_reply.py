from aiogram.utils.keyboard import ReplyKeyboardBuilder


def res_admin_keyboard():
    """Создаёт reply-клавиатуру для админ-панели резидента.
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text="🎁 Начислить бонусы")
    builder.button(text="💸 Списать бонусы")
    # builder.button(text="🔧 Настройки")
    builder.button(text="🚪 Выход")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)
