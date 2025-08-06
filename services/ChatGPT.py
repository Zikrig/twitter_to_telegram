import logging
from openai import AsyncOpenAI
from config import config

logger = logging.getLogger(__name__)

class ChatGPT:
    def __init__(self):
        self.api_key = config.GPT_API_KEY
        self.model = config.GPT_MODEL
        self.temperature = config.GPT_TEMPERATURE
        self.max_tokens = config.GPT_MAX_TOKENS
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        
        if not self.api_key:
            logger.warning("GPT_API_KEY не установлен! Функции перевода будут недоступны")

    async def generate_translation(self, text: str, prompt_path: str = "prompts/translation_prompt.txt") -> str:
        if not self.client:
            return text
            
        try:
            # Загружаем промпт из файла
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read().strip()
            
            # logger.info('Используем модель: ' + self.model)  # Логируем начало запроса
            # Формируем запрос через новый API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                # temperature=self.temperature,
                # max_tokens=self.max_tokens
            )
            
            # Извлекаем результат
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            return text
        
        except Exception as e:
            logger.exception(f"Ошибка при переводе: {str(e)}")
            return text