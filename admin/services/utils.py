import aiohttp
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from data.config import config_settings
from data.url import url_category, url_resident
from typing import Optional
import pandas as pd
from io import BytesIO
from typing import Tuple, Optional, List, Dict

import logging
logger = logging.getLogger(__name__)


# =================================================================================================
# Для работы с категориями резидентов
# =================================================================================================


async def fetch_categories(tree: bool = False) -> list[dict]:
    """Получение списка категорий из API"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
                f"{url_category}?tree={'true' if tree else 'false'}",
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
        ) as response:
            response.raise_for_status()
            return await response.json()


async def create_category(name: str, parent_id: Optional[int] = None) -> dict:
    """Создание новой категории через API"""
    async with aiohttp.ClientSession() as session:
        data = {"name": name}
        if parent_id:
            data["parent"] = parent_id

        async with session.post(
                url_category,
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
                json=data
        ) as response:
            response.raise_for_status()
            return await response.json()


async def delete_category(category_id: int) -> bool:
    """Удаление категории через API"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(
                f"{url_category}{category_id}/",
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status == 404:
                    logger.error(f"Категория с ID {category_id} не найдена")
                    return False
                response.raise_for_status()
                return response.status == 204
        except Exception as e:
            logger.error(f"Ошибка при удалении категории {category_id}: {str(e)}")
            return False


async def format_categories_list(categories: list) -> str:
    """Форматирует список категорий в едином стиле"""
    if not categories:
        return "📋 Список категорий пуст."

    # Собираем все ID подкатегорий
    subcategory_ids = set()

    def collect_child_ids(cat):
        for child in cat.get('children', []):
            subcategory_ids.add(child['id'])
            collect_child_ids(child)

    for cat in categories:
        collect_child_ids(cat)

    def format_category(cat, level=0):
        # Пропускаем подкатегории при основном выводе
        if level == 0 and cat['id'] in subcategory_ids:
            return ""

        if level == 0:
            prefix = "\n\n" if not cat.get('is_first', False) else ""
            name = f"<b>{cat['name']}</b>"
        else:
            prefix = "    " * level
            name = f" - {cat['name']}"

        children = "\n".join([format_category(child, level + 1) for child in cat.get('children', [])])
        return f"{prefix}{name}{f'\n{children}' if children else ''}"

    if categories:
        categories[0]['is_first'] = True

    categories_list = "".join([format_category(cat) for cat in categories])
    return f"📋 <b>Список категорий резидентов</b>\n\n{categories_list.strip()}"


async def show_categories_message(chat_id: int, bot, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Показывает сообщение со списком категорий в едином стиле"""
    categories = await fetch_categories(tree=True)
    text = await format_categories_list(categories)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup
    )


# =================================================================================================
# Резиденты
# =================================================================================================


async def fetch_categories_with_keyboard(tree: bool = True, cancel_callback: str = "residents_list") -> tuple[
    list[dict], InlineKeyboardMarkup]:
    """
    Получает категории и строит иерархическую клавиатуру (по одной кнопке в ряду)
    Возвращает кортеж (список категорий, клавиатура)
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                    f"{url_category}?tree={'true' if tree else 'false'}",
                    headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ошибка загрузки категорий: {error_text}")

                categories = await response.json()
                builder = InlineKeyboardBuilder()

                # Собираем все ID подкатегорий
                subcategory_ids = set()

                def collect_child_ids(cat):
                    for child in cat.get('children', []):
                        subcategory_ids.add(child['id'])
                        collect_child_ids(child)

                for cat in categories:
                    collect_child_ids(cat)

                def add_category_buttons(cats, level=0):
                    for cat in cats:
                        # Пропускаем подкатегории в основном списке
                        if level == 0 and cat['id'] in subcategory_ids:
                            continue

                        # Добавляем кнопку категории в отдельный ряд
                        btn_text = "    " * level + ("- подкатегория:  " if level > 0 else "") + cat['name']
                        builder.row(InlineKeyboardButton(
                            text=btn_text,
                            callback_data=f"select_category_{cat['id']}"
                        ))

                        # Рекурсивно добавляем дочерние категории
                        if cat.get('children'):
                            add_category_buttons(cat['children'], level + 1)

                add_category_buttons(categories)

                # Добавляем кнопку отмены в отдельный ряд
                builder.row(InlineKeyboardButton(
                    text="◀️ Отмена",
                    callback_data=cancel_callback
                ))

                return categories, builder.as_markup()

        except Exception as e:
            raise Exception(f"Ошибка соединения: {str(e)}")


async def create_resident_api(resident_data: dict) -> tuple[bool, str]:
    """
    Создает нового резидента через API
    Возвращает кортеж (успех, сообщение)
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url_resident,
                json=resident_data,
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status == 201:
                    return True, "✅ Резидент успешно добавлен!"
                else:
                    error_text = await response.text()
                    return False, f"❌ Ошибка при добавлении: {error_text}"
        except Exception as e:
            return False, f"❌ Ошибка соединения: {str(e)}"


async def fetch_residents_list() -> tuple[list[dict] | None, str | None]:
    """
    Получает список резидентов из API
    Возвращает кортеж (список резидентов, None) при успехе или (None, сообщение об ошибке) при ошибке
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                url_resident,
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status == 200:
                    return await response.json(), None
                else:
                    error_text = await response.text()
                    return None, f"❌ Ошибка загрузки: {error_text}"
        except Exception as e:
            return None, f"❌ Ошибка соединения: {str(e)}"


async def generate_residents_excel() -> Tuple[Optional[BytesIO], Optional[str]]:
    """
    Генерирует Excel файл с данными резидентов с улучшенным форматированием.

    Returns:
        Tuple[Optional[BytesIO], Optional[str]]:
            - BytesIO объект с Excel файлом в случае успеха
            - Сообщение об ошибке, если что-то пошло не так
    """
    residents, error = await fetch_residents_list()
    if error:
        return None, error

    try:
        # Создаем DataFrame
        df = pd.DataFrame(residents)

        # Добавляем категории
        for resident in residents:
            categories = ", ".join([cat['name'] for cat in resident.get('categories', [])])
            df.loc[df['id'] == resident['id'], 'categories'] = categories

        # Переименовываем столбцы согласно модели
        column_mapping = {
            'name': 'Наименование',
            'description': 'Описание',
            'info': 'Доп.инфо',
            'working_time': 'График работы',
            'email': 'Email',
            'phone_number': 'Номер телефона',
            'official_website': 'Сайт',
            'address': 'Адрес',
            'building': 'Стр.',
            'entrance': 'Вход',
            'floor': 'Этаж',
            'office': 'Офис/Пом.',
            'photo': 'Фото',
            'pin_code': 'Пин-код',
            'categories': 'Категории'
        }

        # Применяем переименование и оставляем только нужные столбцы
        df = df.rename(columns=column_mapping)
        df = df[column_mapping.values()]

        # Создаем файл в памяти
        output = BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Записываем данные в Excel
            df.to_excel(writer, index=False, sheet_name='Резиденты')

            # Получаем объект листа
            worksheet = writer.sheets['Резиденты']

            # Создаем стили для форматирования
            from openpyxl.styles import Font, Alignment, Border, Side

            # Стиль для заголовков
            header_font = Font(bold=True)
            header_alignment = Alignment(horizontal='center', vertical='center')
            thin_border = Border(left=Side(style='thin'),
                                 right=Side(style='thin'),
                                 top=Side(style='thin'),
                                 bottom=Side(style='thin'))

            # Применяем стиль к заголовкам
            for cell in worksheet[1]:
                cell.font = header_font
                cell.alignment = header_alignment
                cell.border = thin_border

            # Устанавливаем ширину колонок
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter

                # Определяем максимальную длину содержимого
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass

                # Устанавливаем ширину с небольшим запасом
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column_letter].width = adjusted_width

            # Добавляем автофильтр
            worksheet.auto_filter.ref = worksheet.dimensions

            # Стиль для обычных ячеек
            cell_alignment = Alignment(horizontal='left', vertical='center')
            for row in worksheet.iter_rows(min_row=2):
                for cell in row:
                    cell.alignment = cell_alignment

        output.seek(0)
        return output, None

    except Exception as e:
        return None, f"Ошибка генерации Excel: {str(e)}"


async def update_resident_category_api(resident_id: int, category_id: int) -> tuple[bool, str]:
    """
    Обновляет категорию резидента через API

    Args:
        resident_id: ID резидента
        category_id: ID новой категории

    Returns:
        tuple[bool, str]: (успех, сообщение)
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(
                    f"{url_resident}{resident_id}/",
                    json={"category_ids": [category_id]},
                    headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status == 200:
                    return True, "✅ Категория успешно обновлена!"
                error_text = await response.text()
                return False, f"❌ Ошибка обновления: {error_text}"
        except Exception as e:
            return False, f"❌ Ошибка соединения: {str(e)}"


async def update_resident_field_api(
        resident_id: int,
        field: str,
        value: str | int,
        headers: dict
) -> tuple[bool, str, str]:
    """
    Обновляет поле резидента через API

    Args:
        resident_id: ID резидента
        field: Название поля для обновления
        value: Новое значение поля
        headers: Заголовки запроса

    Returns:
        tuple[bool, str, str]: (успех, сообщение, русское название поля)
    """
    FIELD_TRANSLATIONS = {
        "name": "Название",
        "category": "Категория",
        "address": "Адрес",
        "building": "Строение",
        "entrance": "Вход",
        "floor": "Этаж",
        "office": "Офис"
    }

    field_name_ru = FIELD_TRANSLATIONS.get(field, field)
    update_data = {field: value}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(
                    f"{url_resident}{resident_id}/",
                    json=update_data,
                    headers=headers
            ) as response:
                if response.status == 200:
                    return True, f"✅ {field_name_ru} успешно обновлено!", field_name_ru
                error_text = await response.text()
                return False, f"❌ Ошибка обновления: {error_text}", field_name_ru
        except Exception as e:
            return False, f"❌ Ошибка соединения: {str(e)}", field_name_ru


async def fetch_residents_for_deletion() -> tuple[list[dict] | None, str | None]:
    """
    Получает список резидентов для удаления из API

    Returns:
        tuple: (список резидентов, None) при успехе или (None, сообщение об ошибке) при ошибке
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                    url_resident,
                    headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status == 200:
                    return await response.json(), None
                error_text = await response.text()
                return None, f"❌ Ошибка загрузки: {error_text}"
        except Exception as e:
            return None, f"❌ Ошибка соединения: {str(e)}"


async def delete_resident_api(resident_id: str) -> tuple[bool, str]:
    """
    Удаляет резидента через API

    Args:
        resident_id: ID резидента для удаления

    Returns:
        tuple[bool, str]: (успех, сообщение)
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(
                    f"{url_resident}{resident_id}/",
                    headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status == 204:
                    return True, "✅ Резидент успешно удален!"
                error_text = await response.text()
                return False, f"❌ Ошибка удаления: {error_text}"
        except Exception as e:
            return False, f"❌ Ошибка соединения: {str(e)}"


# Для получения данных резидента
async def fetch_resident_data(resident_id: int) -> tuple[Optional[dict], Optional[str]]:
    """Получает данные конкретного резидента по ID"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{url_resident}{resident_id}/",
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status == 200:
                    return await response.json(), None
                error_text = await response.text()
                return None, f"❌ Ошибка загрузки данных резидента: {error_text}"
        except Exception as e:
            return None, f"❌ Ошибка соединения: {str(e)}"

async def fetch_category_name(category_id: int) -> str:
    """Получает название категории по ID"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{url_category}{category_id}/",
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status == 200:
                    category_data = await response.json()
                    return category_data.get('name', 'Неизвестная категория')
                return 'Неизвестная категория'
        except Exception:
            return 'Неизвестная категория'
