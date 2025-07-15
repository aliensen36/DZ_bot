import logging
from datetime import datetime
import platform
import socket
import json
from pathlib import Path
from aiogram import Bot

from utils.filters import ADMIN_CHAT_ID

# Файл для хранения ID последнего сообщения
MESSAGE_ID_FILE = Path("utils/last_message_id.json")

def load_last_message_id() -> int | None:
    """Загружает ID последнего сообщения из файла.

    Returns:
        int | None: ID последнего сообщения или None, если файл отсутствует или произошла ошибка.

    Raises:
        Exception: Если произошла ошибка чтения файла.
    """
    try:
        if MESSAGE_ID_FILE.exists():
            with open(MESSAGE_ID_FILE, "r") as f:
                data = json.load(f)
                return data.get("message_id")
    except Exception as e:
        logging.warning(f"Ошибка загрузки ID сообщения: {e}")
    return None

def save_last_message_id(message_id: int):
    """Сохраняет ID сообщения в файл.

    Args:
        message_id (int): ID сообщения для сохранения.

    Raises:
        Exception: Если произошла ошибка записи в файл.
    """
    try:
        with open(MESSAGE_ID_FILE, "w") as f:
            json.dump({"message_id": message_id}, f)
    except Exception as e:
        logging.error(f"Ошибка сохранения ID сообщения: {e}")

async def notify_restart(bot: Bot, action: str = "перезапущен"):
    """
    Отправляет уведомление админу о состоянии бота с удалением предыдущего
    :param bot: Объект бота
    :param action: Тип события ("остановлен"/"перезапущен")
    """
    try:
        if not ADMIN_CHAT_ID:
            logging.warning("ADMIN_CHAT_ID не настроен. Уведомление не отправлено.")
            return

        # Загружаем ID предыдущего сообщения
        last_msg_id = load_last_message_id()

        # Удаляем предыдущее сообщение, если оно есть
        if last_msg_id:
            try:
                await bot.delete_message(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=last_msg_id
                )
                logging.debug(f"Удалено предыдущее уведомление (ID: {last_msg_id})")
            except Exception as delete_error:
                logging.warning(f"Не удалось удалить сообщение {last_msg_id}: {delete_error}")

        # Собираем системную информацию
        hostname = socket.gethostname()
        system = platform.system()
        time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        # Формируем сообщение
        text = (
            f"⚠️ Бот <b>{action}</b>!\n\n"
            f"• Время: {time}\n"
            f"• Сервер: {hostname} ({system})\n"
        )

        # Отправляем новое сообщение и сохраняем его ID
        sent_message = await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text
        )

        save_last_message_id(sent_message.message_id)
        logging.info(f"Уведомление о {action} отправлено (ID: {sent_message.message_id})")

    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления: {e}", exc_info=True)


        

