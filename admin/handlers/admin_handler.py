import datetime
import logging

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery, InlineKeyboardButton, BufferedInputFile, ContentType
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pandas import NaT, isna

from admin.keyboards.admin_reply import admin_keyboard
from database.models import User
import pandas as pd
from io import BytesIO
from datetime import datetime as dt
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

admin_router = Router()
admin_router.message.filter(
    ChatTypeFilter("private"),
    F.content_type == ContentType.TEXT,
    ~F.text.startswith("/scanqr"), # исключаем /scanqr
    IsGroupAdmin(ADMIN_CHAT_ID, show_message=True)

)



async def generate_excel_report():
    """Генерация отчета в Excel"""
    users = await User.all().values()
    if not users:
        return None

    df = pd.DataFrame(users)

    if 'is_bot' in df.columns:
        df['is_bot'] = df['is_bot'].apply(
            lambda x: 'бот' if x is True else '-'
        )

    datetime_columns = ['created_at', 'updated_at', 'last_activity']
    for col in datetime_columns:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: x.strftime('%Y-%m-%d %H:%M:%S')
                if not isna(x) and hasattr(x, 'strftime')
                else None
            )

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Users')
        worksheet = writer.sheets['Users']
        from openpyxl.styles import Alignment
        alignment = Alignment(
            horizontal='left',
            vertical='center',
            wrap_text=True
        )

        for row in worksheet.iter_rows():
            for cell in row:
                cell.alignment = alignment

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

        from openpyxl.styles import Font, PatternFill, Border, Side
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
async def admin_panel(message: Message):
    logger.info(f"Admin access by {message.from_user.id}")
    await message.answer(
        "🛠 Админ-панель",
        reply_markup=admin_keyboard()
    )


@admin_router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message):
    try:
        # Получаем общее количество пользователей
        total_users = await User.all().count()

        # Создаем инлайн-клавиатуру
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="📥 Выгрузить в Excel",
            callback_data="export_users_excel"
        ))

        await message.answer(
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <code>{total_users}</code>",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Error in show_statistics: {e}")
        await message.answer("⚠️ Произошла ошибка при получении статистики")


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
        reply_markup=ReplyKeyboardRemove()
    )
