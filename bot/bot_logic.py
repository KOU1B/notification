from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import asyncio
from datetime import datetime, timezone

from .config_loader import config
from .db_utils import (
    add_admin, is_admin, get_admins, register_group, get_groups,
    add_service, get_services, delete_service, get_uptime_info,
    get_last_check, get_consecutive_failures
)
from .models import create_db_and_tables

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="logs/bot.log"
)

bot = Bot(token=config['telegram']['token'])
dp = Dispatcher()

# Состояния FSM
class AddService(StatesGroup):
    choosing_group = State()
    choosing_type = State()
    entering_address = State()
    entering_name = State()
    entering_limit = State()

class AddAdmin(StatesGroup):
    entering_id = State()

# Проверка на права администратора (для сообщений и колбэков)
async def check_admin(user_id: int) -> bool:
    return is_admin(user_id) or user_id == config['telegram']['main_admin_id']

@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Автоматическое добавление главного админа из конфига
    if message.from_user.id == config['telegram']['main_admin_id']:
        add_admin(message.from_user.id, message.from_user.username)

    if is_admin(message.from_user.id):
        kb = [
            [InlineKeyboardButton(text="Управление сервисами", callback_data="manage_services")],
            [InlineKeyboardButton(text="Статус всех сервисов", callback_data="status_all")],
            [InlineKeyboardButton(text="Uptime статистика", callback_data="uptime_stats")],
            [InlineKeyboardButton(text="Добавить администратора", callback_data="add_admin")],
            [InlineKeyboardButton(text="Управление группами", callback_data="manage_groups")]
        ]
        await message.answer("Добро пожаловать в панель управления мониторингом!", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await message.answer("Бот мониторинга запущен. Если вы администратор, убедитесь, что ваш ID прописан в конфиге.")

@dp.message(Command("register_group"))
async def cmd_register_group(message: Message):
    if message.chat.type in ["group", "supergroup"]:
        register_group(message.chat.id, message.chat.title)
        await message.answer(f"Группа '{message.chat.title}' успешно зарегистрирована для уведомлений.")
    else:
        await message.answer("Эту команду нужно вызывать в группе.")

# Обработчики Callback-запросов
@dp.callback_query(F.data == "manage_services")
async def manage_services(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return await callback.answer("У вас нет прав администратора.", show_alert=True)
    kb = [
        [InlineKeyboardButton(text="Добавить сервис", callback_data="add_service_start")],
        [InlineKeyboardButton(text="Список сервисов (Удаление)", callback_data="list_services")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ]
    await callback.message.edit_text("Управление сервисами:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "add_service_start")
async def add_service_step1(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return await callback.answer("У вас нет прав администратора.", show_alert=True)
    groups = get_groups()
    if not groups:
        await callback.answer("Сначала зарегистрируйте хотя бы одну группу командой /register_group в чате.", show_alert=True)
        return

    kb = []
    for g in groups:
        kb.append([InlineKeyboardButton(text=g.title, callback_data=f"select_group_{g.id}")])
    kb.append([InlineKeyboardButton(text="Отмена", callback_data="manage_services")])

    await callback.message.edit_text("Выберите группу для уведомлений:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(AddService.choosing_group)

@dp.callback_query(F.data.startswith("select_group_"), AddService.choosing_group)
async def add_service_step2(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.split("_")[-1])
    await state.update_data(group_id=group_id)

    kb = [
        [InlineKeyboardButton(text="HTTP (URL)", callback_data="type_url")],
        [InlineKeyboardButton(text="ICMP (Ping/IP)", callback_data="type_ip")],
        [InlineKeyboardButton(text="Отмена", callback_data="manage_services")]
    ]
    await callback.message.edit_text("Выберите тип проверки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(AddService.choosing_type)

@dp.callback_query(F.data.startswith("type_"), AddService.choosing_type)
async def add_service_step3(callback: CallbackQuery, state: FSMContext):
    service_type = callback.data.split("_")[1]
    await state.update_data(type=service_type)

    await callback.message.edit_text(f"Введите {'URL' if service_type == 'url' else 'IP адрес'}:")
    await state.set_state(AddService.entering_address)

@dp.message(AddService.entering_address)
async def add_service_step4(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("Введите название для этого сервиса:")
    await state.set_state(AddService.entering_name)

@dp.message(AddService.entering_name)
async def add_service_step5(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько раз присылать уведомление при падении?")
    await state.set_state(AddService.entering_limit)

@dp.message(AddService.entering_limit)
async def add_service_final(message: Message, state: FSMContext):
    try:
        limit = int(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введите число.")
        return

    data = await state.get_data()
    add_service(data['name'], data['type'], data['address'], data['group_id'], limit)
    await message.answer(f"Сервис '{data['name']}' успешно добавлен!")
    await state.clear()
    # Возвращаемся в главное меню
    await cmd_start(message)

@dp.callback_query(F.data == "list_services")
async def list_services(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return await callback.answer("У вас нет прав администратора.", show_alert=True)
    services = get_services()
    if not services:
        await callback.answer("Список сервисов пуст.")
        return

    kb = []
    for s in services:
        kb.append([InlineKeyboardButton(text=f"❌ {s.name} ({s.address})", callback_data=f"delete_service_{s.id}")])
    kb.append([InlineKeyboardButton(text="Назад", callback_data="manage_services")])

    await callback.message.edit_text("Нажмите на сервис, чтобы удалить его:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("delete_service_"))
async def handle_delete_service(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return await callback.answer("У вас нет прав администратора.", show_alert=True)
    service_id = int(callback.data.split("_")[-1])
    if delete_service(service_id):
        await callback.answer("Сервис удален.")
        await list_services(callback)
    else:
        await callback.answer("Ошибка при удалении.")

@dp.callback_query(F.data == "status_all")
async def status_all(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return await callback.answer("У вас нет прав администратора.", show_alert=True)
    services = get_services()
    if not services:
        await callback.message.answer("Нет сервисов для мониторинга.")
        return

    text = "📊 **Текущий статус сервисов:**\n\n"
    for s in services:
        last_check = get_last_check(s.id)
        status_icon = "✅ UP" if (last_check and last_check.status) else "❌ DOWN"
        if not last_check: status_icon = "⏳ Ожидает проверки"
        text += f"• **{s.name}**: {status_icon} ({s.address})\n"

    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "uptime_stats")
async def uptime_stats(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return await callback.answer("У вас нет прав администратора.", show_alert=True)
    services = get_services()
    if not services:
        await callback.message.answer("Нет сервисов для статистики.")
        return

    text = "⏱ **Статистика Uptime (Дней без падений):**\n\n"
    now = datetime.now(timezone.utc)
    for s in services:
        last_failure_or_start = get_uptime_info(s.id)
        if last_failure_or_start:
            delta = now - last_failure_or_start
            days = delta.days
            text += f"• **{s.name}**: {days} дн. (с {last_failure_or_start.strftime('%d.%m.%Y %H:%M')})\n"
        else:
            text += f"• **{s.name}**: Нет данных\n"

    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "add_admin")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        return await callback.answer("У вас нет прав администратора.", show_alert=True)
    if callback.from_user.id != config['telegram']['main_admin_id']:
        await callback.answer("Только главный администратор может добавлять других.", show_alert=True)
        return
    await callback.message.answer("Введите Telegram ID нового администратора:")
    await state.set_state(AddAdmin.entering_id)

@dp.message(AddAdmin.entering_id)
async def add_admin_final(message: Message, state: FSMContext):
    try:
        new_id = int(message.text)
        add_admin(new_id)
        await message.answer(f"Администратор с ID {new_id} добавлен.")
    except ValueError:
        await message.answer("Некорректный ID.")
    await state.clear()
    await cmd_start(message)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await cmd_start(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data == "manage_groups")
async def manage_groups(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return await callback.answer("У вас нет прав администратора.", show_alert=True)
    groups = get_groups()
    text = "📋 **Зарегистрированные группы:**\n\n"
    for g in groups:
        text += f"• {g.title} (ID: {g.tg_id})\n"
    text += "\nЧтобы добавить группу, добавьте бота в чат и введите /register_group"
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()
