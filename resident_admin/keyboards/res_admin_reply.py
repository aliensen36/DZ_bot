from aiogram.utils.keyboard import ReplyKeyboardBuilder


def res_admin_keyboard():
    """Создаёт reply-клавиатуру для админ-панели резидента.
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text="Бонусы")
    builder.button(text="Акции")
    # builder.button(text="Настройки")
    builder.button(text="Выход")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# Создаёт reply-клавиатуру для админ-панели резидента в разделе "Бонусы"
def res_admin_promotion_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Создать акцию")
    builder.button(text="Изменить акцию")
    builder.button(text="Удалить акцию")
    builder.button(text="↩ Обратно")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Создаёт reply-клавиатуру для отмены действий в админ-панели резидента
def res_admin_cancel_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Сбросить")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

# Создаёт reply-клавиатуру для редактирования акция в админ-панели резидента
def res_admin_edit_promotion_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Пропустить")
    builder.button(text="Сбросить")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)