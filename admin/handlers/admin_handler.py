import logging
from urllib.parse import urlparse
import aiohttp
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from aiohttp import ClientError, ClientConnectionError, ServerTimeoutError
import socket
from admin.keyboards.admin_reply import admin_keyboard
import pandas as pd
from io import BytesIO
from datetime import datetime as dt

from client.keyboards.reply import main_kb
from data.url import url_users
from data.config import config_settings
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

BOT_API_KEY = config_settings.bot_api_key.get_secret_value()


admin_router = Router()
admin_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin(ADMIN_CHAT_ID, show_message=True)
)


async def generate_excel_report():
    """
    Генерация отчета в Excel с данными пользователей
    """
    if not BOT_API_KEY:
        logger.error("BOT_API_KEY не установлен")
        return None

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                    url_users,
                    headers={'X-API-Key': BOT_API_KEY}
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Ошибка при получении пользователей: {resp.status}, {error_text}")
                    return None
                users = await resp.json()
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}")
            return None

    if not users:
        return None

    # Создаем DataFrame и исключаем ненужные столбцы
    columns_to_drop = ['id', 'password']  # Список столбцов для удаления
    df = pd.DataFrame(users).drop(columns=columns_to_drop, errors='ignore')

    # Применяем преобразования к полям
    bool_columns = ['is_bot', 'is_staff', 'is_active', 'is_superuser']
    for col in bool_columns:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: 'Да' if x else 'Нет')

    datetime_columns = ['date_joined', 'last_activity']
    for col in datetime_columns:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: x[:19].replace('T', ' ') if isinstance(x, str) else None
            )

    # Переименовываем колонки для красивого отображения
    column_mapping = {
        'tg_id': 'TG ID',
        'username': 'Никнейм',
        'first_name': 'Имя',
        'last_name': 'Фамилия',
        'is_bot': 'Бот',
        'date_joined': 'Дата регистрации',
        'last_activity': 'Последняя активность',
        'is_staff': 'Админ',
        'is_active': 'Активный',
        'is_superuser': 'Суперюзер'
    }
    df.rename(columns=column_mapping, inplace=True)

    # Создаем Excel-файл
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Пользователи')
        worksheet = writer.sheets['Пользователи']

        # Настройка выравнивания
        alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        for row in worksheet.iter_rows():
            for cell in row:
                cell.alignment = alignment

        # Автоподбор ширины колонок
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            worksheet.column_dimensions[column_letter].width = adjusted_width

        # Стилизация заголовков
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        for cell in worksheet[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center', vertical='center')

    output.seek(0)
    return output


@admin_router.message(Command("admin"))
async def admin_panel(message: Message, bot: Bot):
    user_id = message.from_user.id
    await message.answer(
        "🛠 Админ-панель",
        reply_markup=admin_keyboard()
    )


@admin_router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message):
    try:
        # Проверка соединения с сервером
        try:
            parsed_url = urlparse(url_users)
            host = parsed_url.hostname
            port = parsed_url.port or (80 if parsed_url.scheme == 'http' else 443)
            with socket.create_connection((host, port), timeout=3):
                pass
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.error(f"Сервер недоступен: {e}")
            await message.answer("🔴 Сервер статистики временно недоступен. Попробуйте позже.")
            return
        except Exception as e:
            logger.error(f"Ошибка проверки соединения: {e}")
            await message.answer("⚠️ Ошибка при проверке доступности сервера")
            return

        if not BOT_API_KEY:
            logger.error("BOT_API_KEY не установлен")
            await message.answer("⚠️ Ошибка конфигурации сервера")
            return

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            try:
                async with session.get(
                    url_users,
                    headers={'X-API-Key': BOT_API_KEY}
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"API error {resp.status}: {error_text}")
                        await message.answer(f"⚠️ Ошибка сервера {resp.status}. Попробуйте позже.")
                        return
                    try:
                        users = await resp.json()
                    except ValueError as e:
                        logger.error(f"Invalid JSON response: {e}")
                        await message.answer("⚠️ Ошибка обработки данных сервера")
                        return
            except ServerTimeoutError as e:
                logger.error(f"Timeout error: {e}")
                await message.answer("⏳ Сервер не отвечает. Попробуйте позже.")
                return
            except ClientConnectionError as e:
                logger.error(f"Connection error: {e}")
                await message.answer("🔴 Не удалось подключиться к серверу")
                return
            except ClientError as e:
                logger.error(f"Client error: {e}")
                await message.answer("⚠️ Ошибка при запросе к серверу")
                return

        # Обработка данных
        total_users = len(users)
        active_users = sum(1 for user in users if user.get('is_active', False))

        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="📥 Выгрузить в Excel",
            callback_data="export_users_excel"
        ))

        await message.answer(
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <code>{total_users}</code>\n"
            f"🟢 Активных: <code>{active_users}</code>",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Unexpected error in show_statistics: {e}", exc_info=True)
        await message.answer("⚠️ Непредвиденная ошибка при получении статистики")


@admin_router.callback_query(F.data == "export_users_excel")
async def export_users_excel(callback: CallbackQuery):
    try:
        await callback.answer("⏳ Готовим отчет...")
        excel_file = await generate_excel_report()

        if excel_file:
            await callback.message.answer_document(
                BufferedInputFile(
                    excel_file.getvalue(),
                    filename=f"users_report_{dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"  # Используем dt вместо datetime
                ),
                caption="📊 Полный отчет по пользователям"
            )
        else:
            await callback.message.answer("❌ Нет данных для выгрузки")
    except Exception as e:
        logger.error(f"Error in export_users_excel: {e}", exc_info=True)
        await callback.message.answer("⚠️ Произошла ошибка при генерации отчета")
    finally:
        await callback.answer()


@admin_router.message(F.text == "🚪 Выход")
async def exit_admin_panel(message: Message):
    await message.answer(
        "Выход из админ-панели",
        reply_markup=main_kb
    )
