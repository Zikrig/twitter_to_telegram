# editor.py
from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.orm import Session
import re

from ..database import SessionLocal
from ..utils import *
from services.Twitter import Twitter
from config import config
from .utils import *

class EditorStates(StatesGroup):
    waiting_for_channel_name = State()
    
router = Router()

@router.message(F.text == "➕ Добавить канал")
async def start_add_channel(message: types.Message, state: FSMContext):
    telegram_id = str(message.from_user.id)

    with SessionLocal() as db:
        editor = get_editor_by_telegram_id(db, telegram_id)
        if not editor and not config.is_admin(message.from_user.id):
            return await message.answer("❌ Вы не зарегистрированы как редактор")

        await state.set_state(EditorStates.waiting_for_channel_name)
        await state.update_data(editor_id=editor.id if editor else None)
    
    await message.answer(
        "Введите название Twitter канала (без @):\n\n"
        "Можно отменить действие кнопкой ниже:",
        reply_markup=build_cancel_keyboard()
    )

# Обработчик отмены для состояния добавления канала
@router.callback_query(F.data == "cancel_action", EditorStates.waiting_for_channel_name)
async def cancel_add_channel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление канала отменено")
    await callback.answer()


@router.message(EditorStates.waiting_for_channel_name)
async def process_add_channel(message: types.Message, state: FSMContext):
    """Обработка ввода названия канала"""
    data = await state.get_data()
    editor_id = data.get("editor_id")
    channel_name = message.text.strip().replace("@", "")
    
    pattern = re.compile(r'^[a-zA-Z0-9_]{1,15}$')
    if not pattern.match(channel_name):
        await message.answer(
            "❌ Неверный формат. Используйте латиницу без пробелов.\n\n"
            "Попробуйте еще раз или отмените действие:",
            reply_markup=build_cancel_keyboard()
        )
        return
    
    await state.clear()  # Очищаем состояние после успешной обработки  

    with SessionLocal() as db:
        # Для админа создаем временного редактора если нужно
        if editor_id is None and config.is_admin(message.from_user.id):
            telegram_id = str(message.from_user.id)
            editor = get_editor_by_telegram_id(db, telegram_id)
            if not editor:
                editor = create_editor(db, telegram_id, "Admin")
            editor_id = editor.id
        
        editor = get_editor_by_id(db, editor_id)
        if not editor:
            await message.answer("❌ Редактор не найден.")
            return
        
        twitter_client = Twitter(config.TWITTER_API_HOST, config.TWITTER_API_KEY)
        user_info = twitter_client.get_user_by_username(channel_name)

        if user_info['error'] == 'true':
            return await message.answer(f"❌ Ошибка: {user_info.get('data', 'Канал не найден')}")
        
        rest_id = user_info['data']

        channel_data = {
            "name": channel_name,
            "twitter_id": rest_id,
            "last_post_time": None
        }

        channel = add_channel_to_editor(db, editor.id, channel_data)
        
        if channel:
            await message.answer(f"✅ Канал добавлен: @{channel_name} (Twitter ID: {rest_id})")
        else:
            await message.answer("❌ Ошибка при добавлении канала")

    await state.clear()


@router.message(F.text == "🗑️ Удалить канал из системы")
async def delete_channel_admin_list(message: types.Message):
    """Показывает список каналов для удаления"""
    telegram_id = str(message.from_user.id)
    
    with SessionLocal() as db:
        # Для админа показываем все каналы
        if config.is_admin(message.from_user.id):
            channels = get_all_channels(db)
        else:
            return
        
    if not channels:
        await message.answer("❌ Каналы не найдены")
        return
    
    builder = InlineKeyboardBuilder()
    for channel in channels:
        # Для админа используем другой callback формат
        if config.is_admin(message.from_user.id):
            callback_data = f"admin_delete_channel:{channel.id}"
        # # else:
        # callback_data = f"delete_channel:{channel.id}:{editor.id if not config.is_admin(message.from_user.id) else ''}"
        
        builder.add(
            types.InlineKeyboardButton(
                text=f"❌ {channel.name} (ID: {channel.twitter_id})",
                callback_data=callback_data
            )
        )
    builder.adjust(1)
    
    await message.answer(
        "Выберите канал для удаления:",
        reply_markup=builder.as_markup()
    )


@router.message(F.text == "➖ Удалить канал")
async def delete_channel_list(message: types.Message):
    """Показывает список каналов для удаления"""
    telegram_id = str(message.from_user.id)
    
    with SessionLocal() as db:
        # Для админа показываем все каналы
        # if config.is_admin(message.from_user.id):
        #     channels = get_all_channels(db)
        # else:
        editor = get_editor_by_telegram_id(db, telegram_id)
        if not editor:
            return await message.answer("❌ Вы не зарегистрированы как редактор")
        channels = get_editor_channels(db, editor.id)
    
    if not channels:
        await message.answer("❌ Каналы не найдены")
        return
    
    builder = InlineKeyboardBuilder()
    for channel in channels:
        # Для админа используем другой callback формат
        # if config.is_admin(message.from_user.id):
        #     callback_data = f"admin_delete_channel:{channel.id}"
        # else:
        callback_data = f"delete_channel:{channel.id}:{editor.id if not config.is_admin(message.from_user.id) else ''}"
        
        builder.add(
            types.InlineKeyboardButton(
                text=f"❌ {channel.name} (ID: {channel.twitter_id})",
                callback_data=callback_data
            )
        )
    builder.adjust(1)
    
    await message.answer(
        "Выберите канал для удаления:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("delete_channel:"))
async def delete_channel_callback(callback: types.CallbackQuery):
    """Удаление выбранного канала (для редакторов)"""
    _, channel_id, editor_id = callback.data.split(":")
    channel_id = int(channel_id)
    editor_id = int(editor_id)
    
    with SessionLocal() as db:
        if remove_channel_from_editor(db, editor_id, channel_id):
            await callback.message.edit_text("✅ Канал успешно удалён")
        else:
            await callback.message.edit_text("❌ Ошибка при удалении канала")
    
    await callback.answer()

@router.callback_query(F.data.startswith("admin_delete_channel:"))
async def admin_delete_channel_callback(callback: types.CallbackQuery):
    """Удаление выбранного канала (для админов)"""
    channel_id = int(callback.data.split(":")[1])
    
    with SessionLocal() as db:
        if delete_channel(db, channel_id):
            await callback.message.edit_text("✅ Канал полностью удалён из системы")
        else:
            await callback.message.edit_text("❌ Ошибка при удалении канала")
    
    await callback.answer()

@router.message(F.text == "📋 Мои каналы")
async def my_channels_handler(message: types.Message):
    """Показывает список каналов пользователя"""
    telegram_id = str(message.from_user.id)
    
    with SessionLocal() as db:
        if config.is_admin(message.from_user.id):
            editor = get_editor_by_telegram_id(db, telegram_id)
            if not editor:
                return await message.answer("❌ Админ не зарегистрирован как редактор")
            channels = get_editor_channels(db, editor.id)
        else:
            editor = get_editor_by_telegram_id(db, telegram_id)
            if not editor:
                return await message.answer("❌ Вы не зарегистрированы как редактор")
            channels = get_editor_channels(db, editor.id)
    
    if not channels:
        await message.answer("❌ У вас нет добавленных каналов")
        return
    
    response = ["📋 Ваши каналы:"]
    for channel in channels:
        last_post = channel.last_post_time or "еще не обновлялся"
        response.append(f"• @{channel.name} (ID: {channel.twitter_id}) - последний пост: {last_post}")
    
    await message.answer("\n".join(response))