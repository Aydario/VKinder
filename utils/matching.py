from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import logging
from database import models
from database.crud import (
    get_user,
    get_favorites,
    is_in_blacklist,
    cache_match,
    get_user_state
)
from vkapi.methods import VKUserData, VKSearch, VKPhotos
import json
from difflib import SequenceMatcher
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class CandidateMatcher:
    """
    Класс для поиска и оценки потенциальных партнеров по заданным критериям.
    
    Атрибуты:
        db (Session): Сессия подключения к базе данных
        user_id (int): ID пользователя, для которого выполняется поиск
        vk_user (VKUserData): Объект для работы с данными пользователя VK
        vk_search (VKSearch): Объект для поиска пользователей VK
        vk_photos (VKPhotos): Объект для работы с фотографиями VK
        searcher: Данные пользователя, выполняющего поиск
        search_params: Параметры поиска пользователя
        default_weights (dict): Веса критериев по умолчанию
    """

    def __init__(self, db: Session, user_id: int, vk_token: str):
        """
        Инициализация объекта для поиска кандидатов.
        
        Аргументы:
            db (Session): Сессия подключения к базе данных
            user_id (int): ID пользователя, для которого выполняется поиск
            vk_token (str): Токен для работы с API VK
        """
        self.db = db
        self.user_id = user_id
        self.vk_user = VKUserData(vk_token)
        self.vk_search = VKSearch(vk_token)
        self.vk_photos = VKPhotos(vk_token)
        self.searcher = get_user(db, user_id)
        self.search_params = db.query(models.SearchParams).filter_by(user_id=user_id).first()
        
        # Веса критериев по умолчанию
        self.default_weights = {
            'age': 1.0,
            'city': 0.8,
            'interests': 0.7,
            'groups': 0.6,
            'friends': 0.9
        }

    def _get_weights(self) -> Dict[str, float]:
        """
        Получает веса критериев из параметров поиска пользователя.
        
        Возвращает:
            Dict[str, float]: Словарь с весами критериев. 
                             Если параметры поиска не заданы, возвращает значения по умолчанию.
        """
        if not self.search_params:
            return self.default_weights
            
        return {
            'age': getattr(self.search_params, 'age_weight', 1.0),
            'city': 0.8,  # Фиксированный вес для города
            'interests': getattr(self.search_params, 'interests_weight', 0.7),
            'groups': getattr(self.search_params, 'groups_weight', 0.6),
            'friends': getattr(self.search_params, 'friends_weight', 0.9)
        }

    def find_candidates(self) -> List[Dict]:
        """
        Основной метод для поиска кандидатов по заданным параметрам.
        
        Возвращает:
            List[Dict]: Список найденных кандидатов с оценкой совпадения, 
                       отсортированный по убыванию оценки.
                       Возвращает пустой список, если кандидаты не найдены.
        """
        if not self.searcher or not self.search_params:
            logger.error(f"User {self.user_id} or search params not found")
            return []
        
        # Добавляем задержку перед поиском
        time.sleep(0.34)  # ~3 запроса в секунду
        
        params = {
            "min_age": self.search_params.min_age,
            "max_age": self.search_params.max_age,
            "gender": "male" if self.searcher.gender == "female" else "female",
            "city": self.searcher.city,
            "has_photo": self.search_params.has_photo
        }
        
        try:
            raw_candidates = self.vk_search.search(params)
        except exceptions.ApiError as e:
            if e.code == 9:  # Flood control
                time.sleep(1)
                raw_candidates = self.vk_search.search(params)
            else:
                raise e
        
        # Получаем сырые результаты поиска
        raw_candidates = self.vk_search.search(params)
        if not raw_candidates:
            logger.info(f"No candidates found for user {self.user_id}")
            return []
            
        # Фильтруем и оцениваем кандидатов
        scored_candidates = []
        for candidate in raw_candidates:
            if self._should_skip_candidate(candidate['id']):
                continue
                
            score = self._calculate_match_score(candidate)
            if score > 0:  # Минимальный порог
                scored_candidates.append({
                    **candidate,
                    'match_score': score,
                    'photos': self._get_candidate_photos(candidate['id'])
                })
        
        # Сортируем по убыванию оценки
        scored_candidates.sort(key=lambda x: x['match_score'], reverse=True)
        
        # Кэшируем результаты
        self._cache_candidates(scored_candidates)
        
        return scored_candidates

    def _should_skip_candidate(self, candidate_id: int) -> bool:
        """
        Проверяет, нужно ли пропускать кандидата при поиске.
        
        Аргументы:
            candidate_id (int): ID проверяемого кандидата
            
        Возвращает:
            bool: True если кандидата нужно пропустить, False если нет
        """
        # Пропускаем себя
        if candidate_id == self.user_id:
            return True
            
        # Проверяем черный список
        if is_in_blacklist(self.db, self.user_id, candidate_id):
            return True
            
        # Проверяем, есть ли уже в избранном
        favorites = [f.favorite_user_id for f in get_favorites(self.db, self.user_id)]
        if candidate_id in favorites:
            return True
            
        return False

    def _calculate_match_score(self, candidate: Dict) -> float:
        """
        Вычисляет оценку совпадения кандидата с параметрами поиска.
        
        Аргументы:
            candidate (Dict): Данные кандидата
            
        Возвращает:
            float: Оценка совпадения (от 0 до максимально возможного значения)
        """
        weights = self._get_weights()
        total_score = 0.0
        
        # Оценка по возрасту
        if self.searcher.age and candidate.get('age'):
            age_diff = abs(self.searcher.age - candidate['age'])
            age_score = max(0, 1 - age_diff / 10)  # Нормализация к 0-1
            total_score += age_score * weights['age']
        
        # Оценка по городу
        if self.searcher.city and candidate.get('city'):
            if self.searcher.city.lower() == candidate['city'].lower():
                total_score += 1 * weights['city']
        
        # Оценка по интересам
        if self.search_params.interests:
            searcher_interests = json.loads(self.search_params.interests)
            candidate_interests = {
                'interests': candidate.get('interests', '').split(','),
                'music': candidate.get('music', '').split(','),
                'books': candidate.get('books', '').split(',')
            }
            interest_score = self._compare_interests(searcher_interests, candidate_interests)
            total_score += interest_score * weights['interests']
        
        # Оценка по группам (если есть доступ)
        try:
            searcher_groups = {g['id'] for g in self.vk_user.get_groups(self.user_id)}
            candidate_groups = {g['id'] for g in self.vk_user.get_groups(candidate['id'])}
            common_groups = searcher_groups & candidate_groups
            group_score = min(1, len(common_groups) / 10)  # Нормализация
            total_score += group_score * weights['groups']
        except Exception as e:
            logger.warning(f"Couldn't compare groups: {e}")
        
        # Оценка по друзьям (если есть доступ)
        try:
            searcher_friends = set(self.vk_user.get_friends(self.user_id))
            candidate_friends = set(self.vk_user.get_friends(candidate['id']))
            common_friends = searcher_friends & candidate_friends
            friends_score = min(1, len(common_friends) / 5)  # Нормализация
            total_score += friends_score * weights['friends']
        except Exception as e:
            logger.warning(f"Couldn't compare friends: {e}")
        
        return round(total_score, 2)

    def _compare_interests(self, interests1: Dict, interests2: Dict) -> float:
        """
        Сравнивает интересы двух пользователей с учетом их схожести.
        
        Аргументы:
            interests1 (Dict): Интересы первого пользователя
            interests2 (Dict): Интересы второго пользователя
            
        Возвращает:
            float: Оценка схожести интересов (от 0 до 1)
        """
        total_score = 0
        categories = ['interests', 'music', 'books']
        
        for category in categories:
            items1 = [i.lower().strip() for i in interests1.get(category, []) if i.strip()]
            items2 = [i.lower().strip() for i in interests2.get(category, []) if i.strip()]
            
            if not items1 or not items2:
                continue
                
            # Сравниваем каждый элемент с каждым
            for item1 in items1:
                for item2 in items2:
                    similarity = SequenceMatcher(None, item1, item2).ratio()
                    if similarity > 0.7:  # Порог схожести
                        total_score += similarity
        
        # Нормализуем оценку
        max_possible = sum(len(v) for v in interests1.values())
        return min(1, total_score / max_possible) if max_possible > 0 else 0

    def _get_candidate_photos(self, candidate_id: int) -> List[Dict]:
        """
        Получает фотографии кандидата для отображения.
        
        Аргументы:
            candidate_id (int): ID кандидата
            
        Возвращает:
            List[Dict]: Список фотографий (до 3), отсортированных по количеству лайков
        """
        photos = []
        try:
            photos = self.vk_photos.get_top_photos(candidate_id)
        except Exception as e:
            logger.warning(f"Error getting profile photos: {e}")
        
        # Пробуем получить фотографии с отметками (если есть права)
        try:
            tagged_photos = self.vk_photos.get_tagged_photos(candidate_id)
            photos.extend(tagged_photos)
        except Exception as e:
            logger.debug(f"Couldn't get tagged photos: {e}")
        
        # Убираем дубликаты и сортируем по лайкам
        unique_photos = {p['id']: p for p in photos}.values()
        return sorted(unique_photos, key=lambda x: x.get('likes', 0), reverse=True)[:3]
        
    def _cache_candidates(self, candidates: List[Dict]) -> None:
        """
        Сохраняет найденных кандидатов в кэш базы данных.
        
        Аргументы:
            candidates (List[Dict]): Список кандидатов для кэширования
        """
        for candidate in candidates:
            existing = self.db.query(models.Match).filter_by(
                user_id=self.user_id,
                matched_user_id=candidate['id']
            ).first()
            
            if existing:
                # Обновляем существующую запись
                existing.match_score = candidate['match_score']
                existing.photos = json.dumps(candidate['photos'])
                existing.last_shown = datetime.now()
            else:
                # Создаем новую запись
                cache_match(
                    self.db,
                    self.user_id,
                    candidate['id'],
                    candidate['photos'],
                    candidate['match_score']
                )
        
        self.db.commit()

    def get_next_candidate(self) -> Optional[Dict]:
        """
        Получает следующего кандидата для показа пользователю.
        
        Возвращает:
            Optional[Dict]: Данные кандидата или None, если кандидатов нет
        """
        # Сначала проверяем кэш
        cached = self.db.query(models.Match).filter_by(
            user_id=self.user_id
        ).order_by(
            models.Match.match_score.desc()
        ).first()
        
        if cached:
            return {
                "id": cached.matched_user_id,
                "first_name": "",
                "last_name": "",
                "domain": "",
                "match_score": cached.match_score,
                "photos": json.loads(cached.photos)
            }
        
        # Если в кэше нет, выполняем новый поиск
        candidates = self.find_candidates()
        return candidates[0] if candidates else None
    
    def _compare_interests(self, interests1: Dict, interests2: Dict) -> float:
        """
        Альтернативный метод сравнения интересов с учетом весов категорий.
        
        Аргументы:
            interests1 (Dict): Интересы первого пользователя
            interests2 (Dict): Интересы второго пользователя
            
        Возвращает:
            float: Оценка схожести интересов (от 0 до 1)
        """
        weights = {
            'music': 0.8,
            'books': 0.7,
            'movies': 0.6,
            'interests': 0.5
        }
        
        total_score = 0
        max_score = 0
        
        for category, weight in weights.items():
            items1 = interests1.get(category, [])
            items2 = interests2.get(category, [])
            
            if items1 and items2:
                common = set(items1) & set(items2)
                category_score = len(common) / max(len(items1), len(items2))
                total_score += category_score * weight
                max_score += weight
        
        return total_score / max_score if max_score > 0 else 0
        