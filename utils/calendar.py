from datetime import datetime, timezone, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from calendar import monthcalendar

MOSCOW_TZ = timezone(timedelta(hours=3))

def get_calendar(year=None, month=None, prefix=""):
    """Генерирует календарь с указанным префиксом для callback'ов."""
    now = datetime.now(MOSCOW_TZ)
    year = year or now.year
    month = month or now.month

    # Проверка корректности года и месяца
    if year < 1900 or year > 9999:  # Ограничение на разумный диапазон лет
        year = now.year
        month = now.month
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    # Формирование клавиатуры
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Заголовок с месяцем и годом
    month_name = datetime(year, month, 1).strftime("%B %Y")
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="<<", callback_data=f"{prefix}prev_month:{month-1}:{year}"),
        InlineKeyboardButton(text=month_name, callback_data="ignore"),
        InlineKeyboardButton(text=">>", callback_data=f"{prefix}next_month:{month+1}:{year}")
    ])
    
    # Дни недели
    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.inline_keyboard.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in days_of_week])
    
    # Календарь
    weeks = monthcalendar(year, month)
    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_str = f"{day:02d}.{month:02d}.{year}"
                row.append(InlineKeyboardButton(text=str(day), callback_data=f"{prefix}select_date:{date_str}"))
        keyboard.inline_keyboard.append(row)
    
    return keyboard

def get_time_keyboard(prefix=""):
    """Генерирует клавиатуру времени с указанным префиксом для callback'ов."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    times = ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]
    time_buttons = [InlineKeyboardButton(text=t, callback_data=f"{prefix}select_time:{t}") for t in times]
    keyboard.inline_keyboard.append(time_buttons)
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="Ввести вручную", callback_data=f"{prefix}manual_time")])
    return keyboard