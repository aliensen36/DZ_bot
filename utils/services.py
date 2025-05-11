import logging
from datetime import datetime
import platform
import socket
from aiogram import Bot

from config import ADMIN_CHAT_ID


async def notify_restart(bot: Bot, action: str = "перезапущен"):
    """
    Отправляет уведомление админу о состоянии бота
    :param bot: Объект бота
    :param action: Тип события ("остановлен"/"перезапущен")
    """
    try:
        if not ADMIN_CHAT_ID:
            logging.warning("ADMIN_CHAT_ID не настроен. Уведомление не отправлено.")
            return

        # Собираем системную информацию
        hostname = socket.gethostname()
        system = platform.system()
        time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        # Формируем сообщение
        text = (
            f"⚠️ Бот был <b>{action}</b>!\n\n"
            f"• Время: {time}\n"
            f"• Сервер: {hostname} ({system})\n"
        )

        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text
        )
        logging.info(f"Уведомление о {action} отправлено админу")

    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления: {e}", exc_info=True)
