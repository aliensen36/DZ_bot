import re
from datetime import datetime

def get_bonus_word_form(amount: int) -> str:
    """Возвращает правильную форму слова 'балл' в зависимости от количества."""
    if 11 <= amount % 100 <= 14:
        return "баллов"
    last_digit = amount % 10
    if last_digit == 1:
        return "балл"
    elif 2 <= last_digit <= 4:
        return "балла"
    else:
        return "баллов"
    

def normalize_phone_number(phone: str) -> str | None:
    """Нормализует номер телефона, возвращает None при ошибке."""
    # Удаляем все, кроме цифр и плюса
    phone = re.sub(r"[^\d+]", "", phone)

    # Нормализация
    if phone.startswith("8") and len(phone) == 11:
        normalized = "+7" + phone[1:]
    elif phone.startswith("7") and len(phone) == 11:
        normalized = "+7" + phone[1:]
    elif phone.startswith("+") and 11 <= len(re.sub(r"\D", "", phone)) <= 15:
        normalized = phone
    else:
        return None

    # Финальная проверка
    if not re.fullmatch(r"^\+\d{11,15}$", normalized):
        return None
    return normalized


def parse_birth_date(date_str: str) -> str | None:
    """Парсит дату рождения в формате ДД.ММ.ГГГГ и возвращает ISO-формат."""
    try:
        birth_date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        return birth_date_obj.date().isoformat()
    except ValueError:
        return None