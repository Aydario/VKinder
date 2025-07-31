"""Модуль для работы с API ВКонтакте.

Содержит классы для взаимодействия с API ВКонтакте:
- Получение данных пользователей
- Поиск пользователей
- Работа с фотографиями
- Проверка авторизации
"""

import vk_api
from vk_api.exceptions import ApiError
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
from config import Config
import logging
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from functools import lru_cache

logger = logging.getLogger(__name__)


class VKUserData:
    """Класс для работы с данными пользователя ВКонтакте.
    
    Предоставляет методы для получения информации о пользователях,
    их друзьях, группах и других данных профиля.
    """

    def __init__(self, access_token: str):
        """Инициализация класса VKUserData.
        
        Args:
            access_token (str): Токен доступа к API ВКонтакте
        """
        self.vk = vk_api.VkApi(
            token=access_token,
            api_version=Config.VK_API_VERSION
        ).get_api()
        self.last_request = 0
        self.delay = 0.34  # ~3 запроса в секунду (лимит API)

    def get_friends(self, user_id: int) -> List[int]:
        """Получает список ID друзей пользователя.
        
        Args:
            user_id (int): ID пользователя ВКонтакте
            
        Returns:
            List[int]: Список ID друзей или пустой список при ошибке
        """
        now = time.time()
        if now - self.last_request < self.delay:
            time.sleep(self.delay - (now - self.last_request))
        
        try:
            self.last_request = time.time()
            return self.vk.friends.get(
                user_id=user_id,
                v=Config.VK_API_VERSION
            ).get('items', [])
        except Exception as e:
            logger.error(f"Ошибка получения списка друзей: {e}")
            return []
    
    def _calculate_age(self, bdate: Optional[str]) -> Optional[int]:
        """Вычисляет возраст из даты рождения.
        
        Args:
            bdate (Optional[str]): Дата рождения в формате DD.MM.YYYY
            
        Returns:
            Optional[int]: Возраст пользователя или None, если дата некорректна
        """
        if not bdate:
            return None
            
        try:
            parts = bdate.split('.')
            if len(parts) == 3:  # Полная дата
                birth_date = datetime.strptime(bdate, "%d.%m.%Y")
                return (datetime.now() - birth_date).days // 365
            return None  # Неполная дата
        except (ValueError, AttributeError):
            logger.warning(f"Некорректный формат даты рождения: {bdate}")
            return None

    def get_city_id(self, city_name: str) -> Optional[int]:
        """Получает ID города по названию.
        
        Args:
            city_name (str): Название города
            
        Returns:
            Optional[int]: ID города или None, если город не найден
        """
        try:
            response = self.vk.database.getCities(
                q=city_name,
                count=1,
                v=Config.VK_API_VERSION
            )
            
            if response and 'items' in response and response['items']:
                return response['items'][0]['id']
            return None
        except Exception as e:
            logger.error(f"Ошибка получения ID города '{city_name}': {e}")
            return None
    
    def get_profile(self, user_id: Optional[int] = None) -> Optional[Dict]:
        """Получает расширенный профиль пользователя.
        
        Args:
            user_id (Optional[int]): ID пользователя ВКонтакте
            
        Returns:
            Optional[Dict]: Словарь с данными профиля или None при ошибке
        """
        try:
            fields = [
                'sex', 'bdate', 'city', 'photo_max_orig',
                'interests', 'music', 'books', 'movies', 'tv',
                'games', 'quotes', 'about', 'domain', 'activities'
            ]
            
            response = self.vk.users.get(
                user_ids=str(user_id) if user_id else '',
                fields=','.join(fields),
                lang='ru',
                v=Config.VK_API_VERSION
            )
            
            if not response or not isinstance(response, list):
                logger.error(f"Некорректный формат ответа от API VK: {response}")
                return None
                
            data = response[0]
            
            # Обработка города
            city = None
            if 'city' in data and isinstance(data['city'], dict):
                city = data['city'].get('title')
            elif 'city' in data and isinstance(data['city'], str):
                city = data['city']
            
            # Формирование данных профиля
            profile_data = {
                "user_id": data.get('id'),
                "first_name": data.get('first_name', ''),
                "last_name": data.get('last_name', ''),
                "age": self._calculate_age(data.get('bdate')),
                "gender": "female" if data.get('sex') == 1 else "male",
                "city": city,
                "photo_url": data.get('photo_max_orig'),
                "domain": data.get('domain', ''),
                "interests": self._parse_interests(data)
            }
            
            logger.debug(f"Данные профиля пользователя {user_id}: {profile_data}")
            return profile_data
            
        except Exception as e:
            logger.error(f"Ошибка получения профиля: {type(e).__name__} - {str(e)}")
            return None

    def _parse_interests(self, data: Dict) -> Dict:
        """Парсит интересы пользователя из данных профиля.
        
        Args:
            data (Dict): Данные профиля пользователя
            
        Returns:
            Dict: Словарь с интересами пользователя по категориям
        """
        interests = {
            "interests": data.get('interests', '').split(',') if data.get('interests') else [],
            "music": data.get('music', '').split(',') if data.get('music') else [],
            "books": data.get('books', '').split(',') if data.get('books') else [],
            "movies": data.get('movies', '').split(',') if data.get('movies') else [],
            "tv": data.get('tv', '').split(',') if data.get('tv') else [],
            "games": data.get('games', '').split(',') if data.get('games') else [],
            "quotes": data.get('quotes', '').split(',') if data.get('quotes') else [],
            "about": data.get('about', '').split(',') if data.get('about') else [],
            "activities": data.get('activities', '').split(',') if data.get('activities') else []
        }
        return {k: [item.strip() for item in v if item.strip()] for k, v in interests.items()}

    def get_groups(self, user_id: int) -> List[Dict]:
        """Получает список групп пользователя.
        
        Args:
            user_id (int): ID пользователя ВКонтакте
            
        Returns:
            List[Dict]: Список групп или пустой список при ошибке
        """
        try:
            response = self.vk.groups.get(
                user_id=user_id,
                extended=1,
                fields='activity',
                count=100,
                v=Config.VK_API_VERSION
            )
            return response.get('items', [])
        except ApiError as e:
            logger.error(f"Ошибка получения списка групп: {e}")
            return []


class VKSearch:
    """Класс для поиска пользователей по заданным критериям."""
    
    def __init__(self, access_token: str):
        """Инициализация класса VKSearch.
        
        Args:
            access_token (str): Токен доступа к API ВКонтакте
        """
        self.vk = vk_api.VkApi(token=access_token).get_api()
        self.access_token = access_token
        self.last_request = 0
        self.delay = 0.34  # Задержка между запросами
    
    def search(self, params: Dict) -> List[Dict]:
        """Выполняет поиск пользователей по заданным параметрам.
        
        Args:
            params (Dict): Параметры поиска:
                - min_age (int): Минимальный возраст
                - max_age (int): Максимальный возраст
                - gender (str): Пол ('male' или 'female')
                - city (str): Название города
                - city_id (int): ID города
                - has_photo (bool): Только с фотографией
                
        Returns:
            List[Dict]: Список найденных пользователей или пустой список при ошибке
        """
        now = time.time()
        if now - self.last_request < self.delay:
            time.sleep(self.delay - (now - self.last_request))
        
        try:
            self.last_request = time.time()
            search_params = {
                "count": 1000,
                "age_from": params.get("min_age", 18),
                "age_to": params.get("max_age", 45),
                "sex": 1 if params.get("gender") == "female" else 2,
                "has_photo": 1 if params.get("has_photo", True) else 0,
                "status": 6,  # Не в активном поиске
                "fields": "photo_max_orig,domain,interests,music,books",
                "v": Config.VK_API_VERSION
            }
            
            if "city_id" in params:
                search_params["city"] = params["city_id"]
            elif "city" in params:
                city_id = VKUserData(self.access_token).get_city_id(params["city"])
                if city_id:
                    search_params["city"] = city_id
            
            response = self.vk.users.search(**search_params)
            items = response.get("items", [])
            
            return [
                {
                    "id": user["id"],
                    "first_name": user["first_name"],
                    "last_name": user["last_name"],
                    "domain": user.get("domain"),
                    "photo": user.get("photo_max_orig"),
                    "interests": user.get("interests"),
                    "music": user.get("music"),
                    "books": user.get("books")
                }
                for user in items
                if not user.get("is_closed", True)  # Пропускаем закрытые профили
            ]
        except Exception as e:
            logger.error(f"Ошибка поиска: {str(e)}")
            return []


class VKPhotos:
    """Класс для работы с фотографиями пользователей."""
    
    def __init__(self, access_token: str):
        """Инициализация класса VKPhotos.
        
        Args:
            access_token (str): Токен доступа к API ВКонтакте
        """
        self.vk = vk_api.VkApi(token=access_token).get_api()
    
    def get_top_photos(self, user_id: int, count: int = 3) -> List[Dict]:
        """Получает топ-N фотографий профиля по количеству лайков.
        
        Args:
            user_id (int): ID пользователя ВКонтакте
            count (int): Количество фотографий (по умолчанию 3)
            
        Returns:
            List[Dict]: Список фотографий или пустой список при ошибке
        """
        try:
            # Получаем все фото профиля
            photos = self.vk.photos.get(
                owner_id=user_id,
                album_id="profile",
                extended=1,
                count=200,
                v=Config.VK_API_VERSION
            )["items"]
            
            # Сортируем по количеству лайков
            photos.sort(key=lambda x: x["likes"]["count"], reverse=True)
            
            # Выбираем лучшие
            top_photos = []
            for photo in photos[:count]:
                # Находим фото максимального качества
                best_size = max(photo["sizes"], key=lambda s: s["height"])
                top_photos.append({
                    "id": photo["id"],
                    "owner_id": photo["owner_id"],
                    "likes": photo["likes"]["count"],
                    "url": best_size["url"],
                    "width": best_size["width"],
                    "height": best_size["height"]
                })
            
            return top_photos
            
        except ApiError as e:
            logger.error(f"Ошибка при получении фото профиля: {str(e)}")
            return []
    
    def get_tagged_photos(self, user_id: int, count: int = 3) -> List[Dict]:
        """Получает фотографии, на которых отмечен пользователь.
        
        Args:
            user_id (int): ID пользователя ВКонтакте
            count (int): Количество фотографий (по умолчанию 3)
            
        Returns:
            List[Dict]: Список фотографий или пустой список при ошибке
        """
        try:
            photos = self.vk.photos.getUserPhotos(
                user_id=user_id,
                extended=1,
                count=count,
                v=Config.VK_API_VERSION
            ).get('items', [])
            
            return [{
                'id': p['id'],
                'owner_id': p['owner_id'],
                'likes': p['likes']['count'] if 'likes' in p else 0,
                'url': max(p['sizes'], key=lambda s: s['height'])['url']
            } for p in photos]
        except Exception as e:
            logger.debug(f"Не удалось получить фотографии с отметками: {e}")
            return []

    def prepare_attachments(self, photos: List[Dict]) -> str:
        """Формирует строку вложений для отправки в сообщении.
        
        Args:
            photos (List[Dict]): Список фотографий
            
        Returns:
            str: Строка вложений для API ВКонтакте
        """
        return ",".join([f"photo{p['owner_id']}_{p['id']}" for p in photos])


class VKAuth:
    """Класс для проверки авторизации и валидности токенов."""
    
    @staticmethod
    def is_token_valid(token: str) -> bool:
        """Проверяет валидность токена доступа.
        
        Args:
            token (str): Токен доступа к API ВКонтакте
            
        Returns:
            bool: True если токен валиден, иначе False
        """
        try:
            vk_api.VkApi(token=token).get_api().users.get()
            return True
        except Exception as e:
            logger.error(f"Ошибка проверки токена: {str(e)}")
            return False
            