# start.py
from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..utils import *
from config import config
from .utils import *

router = Router()

@router.message(Command("start"))
async def start_menu(message: types.Message):
    user_id = message.from_user.id
    telegram_id = str(user_id)

    # 1. Проверка на админа в приоритетном порядке
    if config.is_admin(user_id):
        with SessionLocal() as db:
            # Гарантируем что админ зарегистрирован как редактор
            editor = get_editor_by_telegram_id(db, telegram_id)
            if not editor:
                create_editor(db, telegram_id, "Admin")  # Создаём если отсутствует
                
        await message.answer(
            "👑 Добро пожаловать в админ-панель!",
            reply_markup=build_admin_reply_keyboard()  # Админское меню
        )
        return  # Важно: завершаем обработку здесь

    # 2. Только после этого проверяем обычных редакторов
    with SessionLocal() as db:
        editor = get_editor_by_telegram_id(db, telegram_id)
        if editor:
            await message.answer(
                f"👤 Добро пожаловать, {editor.name}",
                reply_markup=build_editor_reply_keyboard()  # Редакторское меню
            )
            return

    # 3. Доступ запрещён
    await message.answer("🚫 У вас нет доступа к панели управления.")