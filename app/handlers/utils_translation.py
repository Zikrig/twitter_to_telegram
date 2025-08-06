from services.ChatGPT import ChatGPT
from typing import Dict, Any

chatgpt = ChatGPT()

async def translate_post(post: Dict[str, Any], prompt_path: str = "prompts/translation_prompt.txt") -> Dict[str, Any]:
    """
    Переводит текст поста и сохраняет оригинальный текст
    :param post: Словарь с данными поста
    :param prompt_path: Путь к файлу с промптом
    :return: Модифицированный пост с переводом
    """
    # Сохраняем оригинальный текст
    post['original_text'] = post.get('text', '')
    
    # Переводим только если есть текст
    if post['original_text']:
        post['text'] = await chatgpt.generate_translation(post['original_text'], prompt_path)
    
    return post