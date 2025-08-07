import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


from app.database import init_db, SessionLocal
from app.handlers import admin, editor, start
from app.utils import get_schedule_settings
from config import config

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

dp.include_router(start.router)
dp.include_router(admin.router)
dp.include_router(editor.router)

async def on_startup():
    """Действия при запуске бота"""
    init_db()  # Инициализация таблиц БД
    logger.info("✅ База данных инициализирована")
    
    # Запускаем планировщик
    scheduler.start()
    logger.info("⏰ Планировщик запущен")

async def scheduled_update():
    """Запуск обновления по расписанию"""
    logger.info("⏰ Проверка расписания обновления...")
    
    with SessionLocal() as db:
        try:
            settings = get_schedule_settings(db)
            current_time = datetime.today() + timedelta(hours=3)
            current_hour = current_time.hour
            
            # Проверяем, нужно ли запускать сейчас
            schedule_hours = [int(h.strip()) for h in settings.hours.split(",")]
            if current_hour not in schedule_hours:
                logger.debug(f"Текущий час {current_hour} не в расписании {schedule_hours}")
                return
                
            # Проверяем, не запускали ли в этот час
            if settings.last_run and settings.last_run.hour == current_hour:
                logger.debug(f"Обновление уже запускалось в этом часу: {settings.last_run}")
                return
                
            logger.info(f"🚀 Запуск автоматического обновления (час: {current_hour})")
            
            # Обновляем время последнего запуска
            settings.last_run = current_time
            db.commit()
            
            # Запускаем обновление
            await admin.update_and_send_posts(bot=bot)
            logger.info("✅ Автоматическое обновление завершено")
            
        except Exception as e:
            logger.error(f"Ошибка при автоматическом обновлении: {e}")
            # Отправляем ошибку админам
            for admin_id in config.ADMINS:
                try:
                    await bot.send_message(admin_id, f"❌ Ошибка автоматического обновления: {str(e)}")
                except Exception as send_err:
                    logger.error(f"Не удалось отправить ошибку админу {admin_id}: {send_err}")

async def main():
    """Основная функция запуска бота"""
    await on_startup()
    
    # Добавляем задание в планировщик (каждые 30 минут)
    scheduler.add_job(
        scheduled_update,
        trigger=CronTrigger(minute='0,30'),
        max_instances=1
    )
    logger.info("⏳ Планировщик настроен на запуск каждые 30 минут")
    
    # Запускаем бота
    logger.info("🤖 Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.exception("🔥 Критическая ошибка при запуске бота")
    finally:
        # Останавливаем планировщик при выходе
        if scheduler.running:
            scheduler.shutdown()
            logger.info("⏹ Планировщик остановлен")