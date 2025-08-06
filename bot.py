import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.database import init_db
from app.handlers import admin, editor, start
import logging
logging.basicConfig(level=logging.INFO)


bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(start.router)
dp.include_router(admin.router)
dp.include_router(editor.router)

async def on_startup():
    init_db()  # Инициализация таблиц БД

# Запуск бота
async def main():
    # logging.basicConfig(level=logging.INFO)
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())