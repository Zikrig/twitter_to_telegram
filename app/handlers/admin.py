# admin.py
from aiogram import Router, types, F, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta
import logging


from services.Twitter import Twitter
from .utils_postwork import send_twitter_post, get_new_posts
from .utils_translation import translate_post
from ..database import SessionLocal
from ..utils import *
from config import config
from .utils import *


logger = logging.getLogger(__name__)

class AdminStates(StatesGroup):
    waiting_for_editor_data = State()
    
router = Router()

@router.message(F.text == "📋 Все каналы")
async def all_channels_list(message: types.Message):
    """Показывает список всех каналов"""
    if not config.is_admin(message.from_user.id):
        return
        
    with SessionLocal() as db:
        channels = get_all_channels(db)
    
    if not channels:
        await message.answer("❌ Каналы не найдены")
        return
    
    response = ["📋 Все каналы в системе:"]
    for channel in channels:
        editors = [editor.name for editor in channel.editors]
        editors_str = ", ".join(editors) if editors else "нет редактора"
        
        response.append(
            f"• @{channel.name} (ID: {channel.twitter_id})\n"
            f"  Последний пост: {channel.last_post_time or 'еще не обновлялся'}\n"
            f"  Редакторы: {editors_str}"
        )
    
    await message.answer("\n".join(response))

@router.message(F.text == "➕ Добавить редактора")
async def add_editor_handler(message: types.Message, state: FSMContext):
    """Обработка добавления редактора с кнопкой отмены"""
    if not config.is_admin(message.from_user.id):
        return
        
    await state.set_state(AdminStates.waiting_for_editor_data)
    await message.answer(
        "Введите Telegram ID и имя нового редактора через пробел:\n"
        "Например: <code>123456789 Иван</code>\n\n"
        "Можно отменить действие кнопкой ниже:",
        reply_markup=build_cancel_keyboard()
    )

@router.callback_query(F.data == "cancel_action", AdminStates.waiting_for_editor_data)
async def cancel_add_editor(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Добавление редактора отменено")
    await callback.answer()
    
    
@router.message(F.text == "➖ Удалить редактора")
async def delete_editor_list_handler(message: types.Message):
    """Показывает список редакторов для удаления"""
    if not config.is_admin(message.from_user.id):
        return
        
    with SessionLocal() as db:
        editors = get_all_editors(db)
    
    if not editors:
        await message.answer("❌ Редакторы не найдены")
        return
    
    builder = InlineKeyboardBuilder()
    for editor in editors:
        builder.add(
            types.InlineKeyboardButton(
                text=f"❌ {editor.name} (ID: {editor.telegram_id})",
                callback_data=f"delete_editor:{editor.id}"
            )
        )
    builder.adjust(1)
    
    await message.answer(
        "Выберите редактора для удаления:",
        reply_markup=builder.as_markup()
    )

@router.message(AdminStates.waiting_for_editor_data, F.text.regexp(r'^\d+\s+\w+'))
async def process_add_editor(message: types.Message, state: FSMContext):
    """Обработка ввода данных нового редактора"""
    if not config.is_admin(message.from_user.id):
        return
    await state.clear()
    
    parts = message.text.split(maxsplit=1)
    telegram_id = parts[0]
    name = parts[1]
    
    with SessionLocal() as db:
        editor = create_editor(db, telegram_id, name)
        if editor:
            await message.answer(f"✅ Редактор {name} (ID: {telegram_id}) успешно добавлен!")
        else:
            await message.answer("❌ Ошибка при добавлении редактора")

@router.callback_query(F.data.startswith("delete_editor:"))
async def delete_editor_callback(callback: types.CallbackQuery):
    """Удаление выбранного редактора"""
    editor_id = int(callback.data.split(":")[1])
    
    with SessionLocal() as db:
        editor = get_editor_by_id(db, editor_id)
        if editor and delete_editor(db, editor.telegram_id):
            await callback.message.edit_text(
                f"✅ Редактор {editor.name} успешно удалён"
            )
        else:
            await callback.message.edit_text("❌ Ошибка при удалении редактора")
    
    await callback.answer()


@router.message(Command("update"))
async def update_and_send_posts(message: types.Message, bot: Bot):
    """Обновляет и отправляет новые посты всем подписчикам"""
    if not config.is_admin(message.from_user.id):
        return

    with SessionLocal() as db:
        channels = db.query(models.Channel).options(joinedload(models.Channel.editors)).all()

        if not channels:
            await message.answer("❌ В системе нет каналов для обновления")
            return

        twitter_client = Twitter(config.TWITTER_API_HOST, config.TWITTER_API_KEY)
        rate_limit_reports = []
        total_new_posts = 0

        for channel in channels:
            last_checked = None
            if channel.last_post_time:
                try:
                    last_checked = datetime.strptime(channel.last_post_time, "%Y-%m-%d-%H-%M-%S")
                except ValueError:
                    last_checked = None

            try:
                result = await get_new_posts(
                    twitter_client=twitter_client,
                    channel_twitter_id=channel.twitter_id,
                    last_checked_time=last_checked,
                    bot=bot,
                    admin_ids=config.ADMINS
                )
            except Exception as e:
                await bot.send_message(message.from_user.id, f"⚠️ Ошибка при получении постов для {channel.name}: {e}")
                continue

            if not result:
                continue

            new_posts, rate_limit_info = result
            rate_limit_reports.append(rate_limit_info)

            if not new_posts:
                continue

            recipients = set(editor.telegram_id for editor in channel.editors)
            recipients.update(config.ADMINS)

            for post in new_posts:
                try:
                    post = await translate_post(post)
                except Exception as e:
                    await bot.send_message(
                        message.from_user.id,
                        f"⚠️ Ошибка при переводе поста: {e}\nПост будет отправлен без перевода."
                    )
                    # Продолжим с оригинальным постом

                for recipient_id in recipients:
                    try:
                        await send_twitter_post(bot, recipient_id, post)
                    except Exception as e:
                        await bot.send_message(
                            message.from_user.id,
                            f"⚠️ Ошибка при отправке поста {recipient_id}: {e}"
                        )

            last_post_time = max(post['created_at'] for post in new_posts)
            channel.last_post_time = last_post_time
            total_new_posts += len(new_posts)

        db.commit()
        # logger.info(rate_limit_reports)
        api_limit_ost = min(rate_limit_reports, key=lambda x: int(x.split('/')[0]))
        
        report = (
            f"📊 Обновление завершено!\n"
            f"• Всего каналов: {len(channels)}\n"
            f"• Новых постов: {total_new_posts}\n\n"
            f"Статус API лимитов:\n" + api_limit_ost
        )

        await bot.send_message(message.from_user.id, report)

