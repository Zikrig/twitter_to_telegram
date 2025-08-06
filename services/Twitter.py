import requests
import json
from typing import List, Dict, Any

from datetime import datetime, timedelta


class Twitter:
    def __init__(self, api_host, api_key):
        self.API_HOST = api_host
        self.API_KEY = api_key

# Общий метод для запроса к апи
    def _make_request(self, endpoint, params):
        """Общий метод для выполнения запросов с обработкой ошибок"""
        headers = {
            "x-rapidapi-key": self.API_KEY,
            "x-rapidapi-host": self.API_HOST
        }
        url = f"https://{self.API_HOST}/{endpoint}"
        
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=10  # Таймаут для защиты от зависаний
            )
            
            # print(response.json())
            # print(params)

            response.raise_for_status()  # Проверка HTTP ошибок

            # print(response.json())
            # print(params)

            return {'response': response.json(), 'headers': response.headers}
        
        except requests.exceptions.HTTPError as errh:
            # Обработка HTTP ошибок (4xx, 5xx)
            error_msg = response.json().get('message', 'Unknown HTTP error') if response.text else str(errh)
            return {
                'error': f'HTTP Error: {errh.response.status_code}',
                'message': error_msg
            }
            
        except requests.exceptions.ConnectionError as errc:
            # Проблемы с подключением
            return {'error': 'Connection Error', 'message': str(errc)}
            
        except requests.exceptions.Timeout as errt:
            # Таймаут запроса
            return {'error': 'Timeout Error', 'message': str(errt)}
            
        except requests.exceptions.RequestException as err:
            # Общие ошибки запросов
            return {'error': 'Request Failed', 'message': str(err)}
            
        except ValueError as errv:
            # Ошибки декодирования JSON
            return {'error': 'JSON Decode Error', 'message': str(errv)}

# Получить JSON из апи по твитам
    def get_user_tweets(self, user: str, count: str, min_created_at_datetime=None, exclude_retweets=True) -> dict:
        """Получение твитов пользователя по ID"""
        data = self._make_request(
            endpoint="user-tweets",
            params={"user": user, "count": count}
        )
        
        
        if 'error' in data:
            return {
                "error": 'true',
                "data": data['error'] + '  ' +data['message'],
                # "rate_limit_limit": data['headers'].get("x-ratelimit-requests-limit"),
                # "rate_limit_remaining": headers.get("x-ratelimit-requests-remaining")
            }
        
        else:
            
            return {
                "error": 'false',
                "data": self.__extract_posts_from_twitter_json(data['response'], min_created_at_datetime, exclude_retweets),
                "rate_limit_limit": data['headers'].get("x-ratelimit-requests-limit"),
                "rate_limit_remaining": data['headers'].get("x-ratelimit-requests-remaining")
            }

# Получить JSON из апи по юзернейму
    def get_user_by_username(self, username: str) -> dict:
        if username.startswith('@'):
            username = username[1:]

        """Получение данных пользователя по имени"""
        data = self._make_request(
            endpoint="user",
            params={"username": username}
        )

        # print(data)
        # print(headers)
        if 'error' in data:
            return {
                "error": 'true',
                "data": data['error'] + '  ' +data['message'],
                # "rate_limit_limit": headers.get("x-ratelimit-requests-limit"),
                # "rate_limit_remaining": headers.get("x-ratelimit-requests-remaining")
            }
        else:   
            return {
                "error": 'false',
                "data": self.__get_user_rest_id(data['response']),                
                "rate_limit_limit": data['headers'].get("x-ratelimit-requests-limit"),
                "rate_limit_remaining": data['headers'].get("x-ratelimit-requests-remaining")
            }

    def extract(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлекает список постов с медиа-вложениями из JSON-ответа Twitter.
        Возвращает список словарей с информацией о каждом посте.
        """
        return self.__extract_posts_from_twitter_json(data)

    def __filter_posts(
        self, 
        posts: List[Dict[str, Any]], 
        min_created_at_datetime: datetime | None = None,
        exclude_retweets: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Фильтрует список постов:
        - Исключает ретвиты (если exclude_retweets=True)
        - Оставляет только посты после указанной даты (если min_created_at задан)
        """
        filtered = posts
        
        min_created_at = self.__datetime_to_filter_format(min_created_at_datetime) if min_created_at_datetime else None
        
        # Фильтрация ретвитов
        if exclude_retweets:
            filtered = [post for post in filtered if not post['retweeted']]
        
        # Фильтрация по времени
        if min_created_at:
            filtered = [post for post in filtered if post['created_at'] > min_created_at]
        
        return filtered


    def __datetime_to_filter_format(self, dt: datetime) -> str:
        """Преобразует datetime в строку формата ГГГГ-ММ-ДД-ЧЧ-ММ-СС"""
        return dt.strftime('%Y-%m-%d-%H-%M-%S')
    
# Распарсить JSON с твитами
    def __extract_posts_from_twitter_json(self, data: Dict[str, Any], min_created_at_datetime=None, exclude_retweets=True) -> List[Dict[str, Any]]:
        """
        Извлекает только видимые посты (исключая ретвиты, цитаты и скрытые элементы) 
        со всеми вложениями из JSON Twitter
        """
        visible_posts = []
        
        # Ищем основную временную шкалу
        timeline_instructions = data.get('result', {}).get('timeline', {}).get('instructions', [])
        
        for instruction in timeline_instructions:
            # Обрабатываем основные записи ленты
            if instruction['type'] == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                for entry in entries:
                    entry_id = entry.get('entryId', '')
                    
                    # Фильтруем только видимые посты
                    if not entry_id.startswith(('tweet-', 'profile-conversation')):
                        continue
                        
                    content = entry.get('content', {})
                    item_content = content.get('itemContent', {})
                    
                    # Обрабатываем только основные твиты
                    if item_content.get('itemType') == 'TimelineTweet':
                        tweet_results = item_content.get('tweet_results', {})
                        tweet = tweet_results.get('result', {})
                        self.__process_tweet(tweet, visible_posts)
            
            # Обрабатываем закрепленный твит
            elif instruction['type'] == 'TimelinePinEntry':
                entry = instruction.get('entry', {})
                content = entry.get('content', {})
                item_content = content.get('itemContent', {})
                
                if item_content.get('itemType') == 'TimelineTweet':
                    tweet_results = item_content.get('tweet_results', {})
                    tweet = tweet_results.get('result', {})
                    self.__process_tweet(tweet, visible_posts)
        
        # print(visible_posts)
        filtered_posts = self.__filter_posts(visible_posts, min_created_at_datetime, exclude_retweets)
        # print(filtered_posts)
        return filtered_posts

    
    def __parse_twitter_time(self, time_str):
        # Парсим строку с помощью datetime
        dt = datetime.strptime(time_str, '%a %b %d %H:%M:%S %z %Y')
        
        # Форматируем в строку чисел: ГодМесяцДеньЧасМинутаСекунда
        return dt.strftime('%Y-%m-%d-%H-%M-%S')
    
    def __process_tweet(self, tweet: Dict[str, Any], posts_list: List[Dict[str, Any]]) -> None:
        """Обрабатывает твит и добавляет его в список постов"""
        if tweet.get('__typename') != 'Tweet':
            return
        
        legacy = tweet.get('legacy', {})
        text = legacy.get('full_text', '')
        
        # Основные данные твита
        tweet_data = {
            'id': tweet.get('rest_id', ''),
            'text': text,
            'quote': legacy.get('is_quote_status'),
            'retweeted': text.startswith('RT'),
            'created_at': self.__parse_twitter_time(legacy.get('created_at', '')),
            'media': []
        }
        
        # Извлекаем медиа-вложения
        entities = legacy.get('extended_entities', legacy.get('entities', {}))
        
        if entities and 'media' in entities:
            for media_item in entities['media']:
                media_type = media_item.get('type', '')
                media_url = ''
                
                # Для видео и GIF обрабатываем отдельно
                if media_type in ['video', 'animated_gif']:
                    # Вариант 1: Прямая ссылка на видео в поле 'media_url_https'
                    media_url = media_item.get('media_url_https', '')
                    
                    # Вариант 2: Ссылка на видео в вариантах
                    variants = media_item.get('video_info', {}).get('variants', [])
                    if variants:
                        # Ищем вариант с самым высоким битрейтом
                        variants.sort(key=lambda x: x.get('bitrate', 0), reverse=True)
                        best_variant = variants[0]
                        
                        # Проверяем, является ли ссылка полной
                        url = best_variant.get('url', '')
                        if url.startswith('https://'):
                            media_url = url
                    
                    # Вариант 3: Ссылка на amplify_video (специфичный формат Twitter)
                    if not media_url:
                        media_key = media_item.get('media_key', '')
                        if media_key:
                            media_url = f"https://video.twimg.com/amplify_video/{media_key}/vid/avc1/1080x1920/video.mp4"
                
                # Для фото просто берем ссылку
                elif media_type == 'photo':
                    media_url = media_item.get('media_url_https', '')
                
                if media_url:
                    tweet_data['media'].append({
                        'type': media_type,
                        'url': media_url
                    })
        
        # Добавляем твит в результаты
        posts_list.append(tweet_data)
        
    
# Распарсить JSON с user_id
    def __get_user_rest_id(self, data: Dict[str, Any]) -> str:
        # print(data)
        return data['result']['data']['user']['result']['rest_id']
