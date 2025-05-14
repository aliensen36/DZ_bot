from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(
            text="📲 Открыть приложение",
            web_app=WebAppInfo(url="https://miel.sayrrx.cfd/")
        )
        ]
    ],
    resize_keyboard=True,
    persistent=True,
    input_field_placeholder="Выберите действие"
)