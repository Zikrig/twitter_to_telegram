from aiogram.types import InputMediaPhoto, InputMediaVideo, Message
from aiogram.utils.markdown import hlink
from aiogram import Bot
import re

from datetime import datetime, timedelta
from typing import List, Dict, Any

from services.Twitter import Twitter


async def send_twitter_post(bot: Bot, chat_id: int, post: dict):
    """
    Отправляет пост из Twitter в Telegram с сохранением медиа-вложений
    :param bot: Экземпляр бота aiogram
    :param chat_id: ID чата для отправки
    :param post: Словарь с данными поста из Twitter API
    """
    # Обработка текста поста
    text = post.get('text', '')
    
    # Выделяем ссылки из текста
    links = re.findall(r'https?://\S+', text)
    clean_text = re.sub(r'https?://\S+', '', text).strip()
    
    # Форматируем ссылки как кликабельные
    formatted_links = "\n\n🔗 " + "\n🔗 ".join(links) if links else ""
    
    # Формируем итоговый текст
    formatted_text = f"{clean_text}{formatted_links}" if clean_text or links else ""

    # Обработка медиа-вложений
    media = post.get('media', [])
    
    # Если нет медиа - просто отправляем текст
    if not media:
        if formatted_text:
            await bot.send_message(chat_id, formatted_text)
        return
    
    # Разделяем фото и видео
    photos = [m for m in media if m['type'] == 'photo']
    videos = [m for m in media if m['type'] == 'video']
    
    # Если есть хотя бы одно видео - отправляем первое видео с текстом
    if videos:
            try:
                video_url = videos[0]['url']
                await bot.send_video(
                    chat_id=chat_id,
                    video=video_url,
                    caption=formatted_text[:1024] if formatted_text else None
                )
            except Exception as e:
                # Fallback: отправляем как ссылку
                await bot.send_message(
                    chat_id,
                    f"🎥 Видео: {video_url}\n\n{formatted_text}" if formatted_text else f"🎥 Видео: {video_url}"
                )
    
    # Отправляем фото (если есть)
    if photos:
        # Если фото больше 1 - отправляем как альбом
        if len(photos) > 1:
            media_group = []
            for i, photo in enumerate(photos):
                # Для первого фото добавляем текст
                if i == 0 and formatted_text:
                    media_group.append(
                        InputMediaPhoto(
                            media=photo['url'],
                            caption=formatted_text[:1024]
                        )
                    )
                else:
                    media_group.append(
                        InputMediaPhoto(media=photo['url'])
                    )
            await bot.send_media_group(chat_id, media_group)
        
        # Если только одно фото
        else:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photos[0]['url'],
                caption=formatted_text[:1024] if formatted_text else None
            )
            


async def get_new_posts(
    twitter_client: Twitter,
    channel_twitter_id: str,
    last_checked_time: datetime,
    bot: Bot,
    admin_ids: List[int]
) -> List[Dict[str, Any]]:
    """
    Получает новые посты для канала начиная с последнего времени проверки
    :param twitter_client: Экземпляр клиента Twitter
    :param channel_twitter_id: Twitter ID канала
    :param last_checked_time: Время последней проверки
    :param bot: Экземпляр бота для отправки уведомлений
    :param admin_ids: Список ID администраторов
    :return: Список новых постов
    """
    try:
        # Вычисляем время для фильтрации (последняя проверка или 24 часа назад)
        min_time = last_checked_time if last_checked_time else datetime.today() - timedelta(hours=72)
        
        # Получаем посты через API
        response = twitter_client.get_user_tweets(
            user=channel_twitter_id,
            count="20",  # Получаем последние 20 постов
            min_created_at_datetime=min_time,
            exclude_retweets=True
        )
        
        # Обрабатываем ошибки API
        if response['error'] == 'true':
            error_msg = response.get('data', 'Unknown error')
            for admin_id in admin_ids:
                await bot.send_message(
                    admin_id,
                    f"❌ Ошибка при получении постов для канала {channel_twitter_id}:\n{error_msg}"
                )
            return []
        
        return response['data'], f"Осталось {response['rate_limit_remaining']}/{response['rate_limit_limit']} обращений к API до конца месяца."
    
    except Exception as e:
        # Обрабатываем исключения при работе с API
        error_msg = f"Critical error for channel {channel_twitter_id}: {str(e)}"
        for admin_id in admin_ids:
            await bot.send_message(admin_id, error_msg)
        return []