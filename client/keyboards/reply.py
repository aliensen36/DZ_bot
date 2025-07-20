from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# Клавиатура главного меню
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Личный кабинет")],
        [KeyboardButton(text="Карта лояльности")],
        [KeyboardButton(
            text="Открыть приложение",
            web_app=WebAppInfo(url="https://t.me/DZavodBot?startapp")
        )]
    ],
    resize_keyboard=True,
    persistent=True,
    input_field_placeholder="Выберите действие"
)

# Клавиатура: Редактирование данных
edit_data_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Изменить имя"), KeyboardButton(text="Изменить фамилию")],
        [KeyboardButton(text="Изменить дату рождения"), KeyboardButton(text="Изменить номер телефона")],
        [KeyboardButton(text="Изменить email"), KeyboardButton(text="Вернуться")]
    ],
    resize_keyboard=True
)

# Клавиатура для выхода из FSM, при создании карты
cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отменить")]
    ],
    resize_keyboard=True
)

