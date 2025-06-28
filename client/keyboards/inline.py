from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from client.services.subscriptions import get_subscriptions_name


async def get_profile_inline_kb() -> InlineKeyboardMarkup:
    """
    Асинхронно создает и возвращает inline-клавиатуру для раздела профиля пользователя.
    Клавиатура включает следующие кнопки:
        - "Мои данные": просмотр личных данных пользователя.
        - "Мои подписки": просмотр подписок пользователя.
        - "Назад в главное меню": возврат в главное меню.
    Возвращает:
        InlineKeyboardMarkup: Сконструированная inline-клавиатура.
    """

    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Мои данные",
                             callback_data="my_data"),
        InlineKeyboardButton(text="Мои подписки",
                             callback_data="my_subscriptions"),
        InlineKeyboardButton(text="Назад в главное меню",
                             callback_data="back_to_main")
        ]
    builder.add(*buttons)
    builder.adjust(1)

    return builder.as_markup()


async def build_interests_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    """
    Асинхронно создает inline-клавиатуру для выбора интересов пользователя.
    Каждая опция из доступных подписок отображается отдельной кнопкой. Если опция присутствует в списке `selected`,
    она отмечается галочкой. Клавиатура форматируется для удобства, в конце добавляется кнопка "Готово ✅".
    Аргументы:
        selected (list[str]): Список уже выбранных интересов.
    Возвращает:
        InlineKeyboardMarkup: Сконструированная inline-клавиатура для Telegram-бота.
    """

    builder = InlineKeyboardBuilder()

    options = await get_subscriptions_name()

    for option in options:
        mark = "✅ " if option in selected else ""
        builder.button(
            text=mark + option,
            callback_data=option 
        )

    builder.adjust(2, 2, 2, 1)
    builder.button(text="Готово ✅", callback_data="done")
    return builder.as_markup()


async def no_user_data_inline_kb() -> InlineKeyboardMarkup:
    """
    Асинхронная функция для создания inline-клавиатуры, отображаемой пользователю не зарегистрированному в системе лояльности.
    Возвращает:
        InlineKeyboardMarkup: Объект клавиатуры с кнопками:
            - "Зарегистрироваться" (callback_data="loyalty_register")
            - "Мои подписки" (callback_data="my_subscriptions")
            - "Назад в главное меню" (callback_data="back_to_main")
    """

    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Зарегистрироваться",
                             callback_data="loyalty_register"),
        InlineKeyboardButton(text="Мои подписки",
                             callback_data="my_subscriptions"),
        InlineKeyboardButton(text="Назад в главное меню",
                             callback_data="back_to_main")
        ]
    builder.add(*buttons)
    builder.adjust(1)

    return builder.as_markup()


async def user_data_inline_kb() -> InlineKeyboardMarkup:
    """
    Создаёт и возвращает инлайн-клавиатуру для пользователя с кнопками:
    - "Изменить данные"
    - "Мои подписки"
    - "Назад в главное меню"
    Возвращает:
        InlineKeyboardMarkup: Объект инлайн-клавиатуры для Telegram-бота.
    """

    builder = InlineKeyboardBuilder()

    buttons = [
         InlineKeyboardButton(text="Изменить данные",
                             callback_data="change_user_data"),
        InlineKeyboardButton(text="Мои подписки",
                             callback_data="my_subscriptions"),
        InlineKeyboardButton(text="Назад в главное меню",
                             callback_data="back_to_main")
        ]
    builder.add(*buttons)
    builder.adjust(1)

    return builder.as_markup()


async def bonus_data_inline_kb() -> InlineKeyboardMarkup:
    """
    Создаёт и возвращает инлайн-клавиатуру с кнопками для отображения пользовательских данных, подписок и возврата в главное меню.
    Возвращает:
        InlineKeyboardMarkup: Объект инлайн-клавиатуры с тремя кнопками:
            - "Мои данные"
            - "Мои подписки"
            - "Назад в главное меню"
    """

    builder = InlineKeyboardBuilder()

    buttons = [
         InlineKeyboardButton(text="Мои данные",
                             callback_data="my_data"),
        InlineKeyboardButton(text="Мои подписки",
                             callback_data="my_subscriptions"),
        InlineKeyboardButton(text="Назад в главное меню",
                             callback_data="back_to_main")
        ]
    builder.add(*buttons)
    builder.adjust(1)

    return builder.as_markup()


async def get_back_inline_kb() -> InlineKeyboardMarkup:
    """
    Асинхронная функция для создания инлайн-клавиатуры с одной кнопкой "Вернуться".
    Возвращает:
        InlineKeyboardMarkup: Объект инлайн-клавиатуры с одной кнопкой для возврата.
    """

    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Вернуться")
        ]
    builder.add(*buttons)
    builder.adjust(1)


async def subscription_data_inline_kb() -> InlineKeyboardMarkup:
    """
    Создаёт и возвращает инлайн-клавиатуру для управления подписками пользователя.
    Клавиатура содержит следующие кнопки:
    - "Изменить подписки" — позволяет изменить текущие подписки пользователя.
    - "Мои данные" — отображает личные данные пользователя.
    - "Назад в главное меню" — возвращает в главное меню.
    Возвращает:
        InlineKeyboardMarkup: Объект инлайн-клавиатуры для Telegram-бота.
    """

    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Изменить подписки",
                             callback_data="edit_subscriptions"),
        InlineKeyboardButton(text="Мои данные",
                             callback_data="my_data"),
        InlineKeyboardButton(text="Назад в главное меню",
                             callback_data="back_to_main")
        ]
    builder.add(*buttons)
    builder.adjust(1)

    return builder.as_markup()


async def build_interests_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    """
    Асинхронно создает инлайн-клавиатуру для выбора интересов пользователя.
    Аргументы:
        selected (list[str]): Список выбранных пользователем интересов (названия подписок).
    Возвращает:
        InlineKeyboardMarkup: Объект клавиатуры с кнопками для каждого интереса и кнопкой "Готово".
    Примечания:
        - Выбранные интересы отмечаются галочкой.
        - Для получения списка подписок используется асинхронная функция get_subscriptions_name().
    """

    subscriptions = await get_subscriptions_name()
    keyboard = []
    for sub in subscriptions:
        text = f"✅ {sub}" if sub in selected else f"{sub}"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=sub)])
    keyboard.append([InlineKeyboardButton(text="Готово", callback_data="done")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)