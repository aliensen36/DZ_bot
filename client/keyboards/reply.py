from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="💳 Карта лояльности")],
        [KeyboardButton(
            text="📲 Открыть приложение",
            web_app=WebAppInfo(url="https://design-zavod.tech/")
        )
        ]
    ],
    resize_keyboard=True,
    persistent=True,
    input_field_placeholder="Выберите действие"
)

# Клавиатура: Изменить данные
edit_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✏️ Изменить данные")],
        [KeyboardButton(text="🔙 Вернуться")]
    ],
    resize_keyboard=True
)

# Клавиатура: Редактирование данных
edit_data_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✏️ Изменить имя"), KeyboardButton(text="✏️ Изменить фамилию")],
        [KeyboardButton(text="📅 Изменить дату рождения"), KeyboardButton(text="📞 Изменить номер телефона")],
        [KeyboardButton(text="📧 Изменить email"), KeyboardButton(text="🔙 Вернуться")]
    ],
    resize_keyboard=True
)