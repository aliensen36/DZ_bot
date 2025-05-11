from aiogram.utils.keyboard import ReplyKeyboardBuilder


def admin_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📊 Статистика")
    builder.button(text="📢 Рассылка")
    builder.button(text="🔧 Настройки")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)
