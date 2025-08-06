import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

class Config:
    """Единый класс конфигурации для всего приложения"""
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    ADMIN_IDS = [int(id_str) for id_str in os.getenv('ADMIN_IDS', '').split(',') if id_str]
    
    # Twitter API
    TWITTER_API_HOST = os.getenv('TWITTER_API_HOST', 'twitter241.p.rapidapi.com')
    TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
    
    # GPT
    GPT_API_KEY = os.getenv('GPT_API_KEY')
    GPT_MODEL = os.getenv('GPT_MODEL')
    GPT_TEMPERATURE = float(os.getenv('GPT_TEMPERATURE', '0.7'))
    GPT_MAX_TOKENS = int(os.getenv('GPT_MAX_TOKENS', '1500'))
    
    # Database
    DB_HOST = os.getenv('DB_HOST', 'db')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_USER = os.getenv('DB_USER', 'user')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME', 'mydatabase')
    
    _admins = os.getenv("ADMIN_IDS", "")
    ADMINS = [int(admin_id.strip()) for admin_id in _admins.split(",") if admin_id.strip()] if _admins else []
    
    # App settings
    DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @property
    def DATABASE_URL(self) -> str:
        """Строка подключения к PostgreSQL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    def is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        return user_id in self.ADMIN_IDS

# Создаем экземпляр конфигурации
config = Config()