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
        "Введите Telegram ID (узнать его можно здесь @GetAnyTelegramIdBot) и имя нового редактора через пробел:\n"
        "Например: <code>123456789 Иван</code>\n\n"
        "Можно отменить действие кнопкой ниже:",
        reply_markup=build_cancel_keyboard(),
        parse_mode="HTML"
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
async def manual_update(message: types.Message, bot: Bot):
    """Ручной запуск обновления"""
    if not config.is_admin(message.from_user.id):
        return
        
    await update_and_send_posts(bot)
    
    
async def update_and_send_posts(bot: Bot):
    """Обновляет и отправляет новые посты всем подписчикам"""

    with SessionLocal() as db:
        channels = db.query(models.Channel).options(joinedload(models.Channel.editors)).all()

        if not channels:
            for ADMIN_ID in config.ADMINS:
                await bot.send_message(ADMIN_ID, "❌ В системе нет каналов для обновления")
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
                for ADMIN_ID in config.ADMINS:
                    await bot.send_message(ADMIN_ID, f"⚠️ Ошибка при получении постов для {channel.name}: {e}")
                continue

            if not result:
                continue

            new_posts, rate_limit_info = result
            rate_limit_reports.append(rate_limit_info)

            if not new_posts:
                continue

            recipients = set(editor.telegram_id for editor in channel.editors)
            # recipients.update(config.ADMINS)

            for post in new_posts:
                try:
                    post = await translate_post(post)
                except Exception as e:
                    
                    for ADMIN_ID in config.ADMINS:
                        await bot.send_message(ADMIN_ID, f"⚠️ Ошибка при переводе поста: {e}\nПост будет отправлен без перевода.")

                    # Продолжим с оригинальным постом

                for recipient_id in recipients:
                    try:
                        await send_twitter_post(bot, recipient_id, post)
                    except Exception as e:
                        for ADMIN_ID in config.ADMINS:
                            await bot.send_message(ADMIN_ID, f"⚠️ Ошибка при отправке поста {recipient_id}: {e}")

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
        for ADMIN_ID in config.ADMINS:
            await bot.send_message(ADMIN_ID, report)


@router.message(F.text == "⏰ Управление расписанием")
async def manage_schedule(message: types.Message):
    """Показывает меню управления расписанием"""
    if not config.is_admin(message.from_user.id):
        return
        
    with SessionLocal() as db:
        settings = get_schedule_settings(db)
        hours = settings.hours
        
        builder = InlineKeyboardBuilder()
        # Кнопки для добавления/удаления часов
        for hour in range(0, 24):
            emoji = "✅" if str(hour) in hours.split(",") else "❌"
            builder.add(types.InlineKeyboardButton(
                text=f"{emoji} {hour}:00",
                callback_data=f"schedule_toggle:{hour}"
            ))
        
        builder.adjust(4)  # 4 кнопки в ряд
        
        # Кнопки подтверждения/отмены
        builder.row(
            types.InlineKeyboardButton(
                text="✔️ Сохранить расписание",
                callback_data="schedule_save"
            ),
            types.InlineKeyboardButton(
                text="❌ Отменить",
                callback_data="schedule_cancel"
            )
        )
        
        await message.answer(
            "⏰ Текущее расписание обновлений:\n"
            f"Часы: {hours}\n\n"
            "Выберите часы для автоматического обновления:",
            reply_markup=builder.as_markup()
        )

@router.callback_query(F.data.startswith("schedule_toggle:"))
async def toggle_schedule_hour(callback: types.CallbackQuery):
    """Переключает выбранный час в расписании"""
    hour = callback.data.split(":")[1]
    
    with SessionLocal() as db:
        settings = get_schedule_settings(db)
        hours_list = settings.hours.split(",")
        if '' in hours_list:
            hours_list.remove('')
        
        if hour in hours_list:
            hours_list.remove(hour)
        else:
            hours_list.append(hour)
        
        # logging.info(f"Текущие часы: {hours_list}")
        # Сортируем и обновляем
        # if len(hours_list) > 0:
        hours_list.sort(key=int)
        settings.hours = ",".join(hours_list)
        db.commit()
        # else:
        #     settings.hours = ""
        #     db.commit()            
            
        # Обновляем клавиатуру
        await update_schedule_keyboard(callback.message, settings.hours)
    
    await callback.answer()

async def update_schedule_keyboard(message: types.Message, hours: str):
    """Обновляет инлайн-клавиатуру с текущим расписанием"""
    # Фильтруем пустые значения
    hours_list = [h.strip() for h in hours.split(",") if h.strip()]
    
    builder = InlineKeyboardBuilder()
    
    for hour in range(0, 24):
        # Проверяем наличие часа в списке как числа
        emoji = "✅" if str(hour) in hours_list else "❌"
        builder.add(types.InlineKeyboardButton(
            text=f"{emoji} {hour}:00",
            callback_data=f"schedule_toggle:{hour}"
        ))
    
    builder.adjust(4)
    builder.row(
        types.InlineKeyboardButton(
            text="✔️ Сохранить расписание",
            callback_data="schedule_save"
        ),
        types.InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="schedule_cancel"
        )
    )
    
    await message.edit_text(
        f"⏰ Текущее расписание обновлений:\nЧасы: {hours}\n\n"
        "Выберите часы для автоматического обновления:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "schedule_save")
async def save_schedule(callback: types.CallbackQuery):
    """Сохраняет расписание и закрывает меню"""
    with SessionLocal() as db:
        settings = get_schedule_settings(db)
        await callback.message.edit_text(
            f"✅ Расписание сохранено!\nЧасы обновления: {settings.hours}"
        )
    await callback.answer()

@router.callback_query(F.data == "schedule_cancel")
async def cancel_schedule(callback: types.CallbackQuery):
    """Отменяет изменения и закрывает меню"""
    with SessionLocal() as db:
        # Восстанавливаем предыдущее расписание
        settings = get_schedule_settings(db)
        original_hours = settings.hours
        db.rollback()  # Отменяем изменения
        
        await callback.message.edit_text(
            f"❌ Изменения отменены\nТекущее расписание: {original_hours}"
        )
    await callback.answer()