"""Модуль для работы с базой данных (CRUD операции).

Содержит функции для создания, чтения, обновления и удаления данных
пользователей, их настроек поиска, избранного и черного списка.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import json
from . import models
import logging
from utils.states import BotState

logger = logging.getLogger(__name__)


def create_user(db: Session, user_data: Dict) -> Optional[models.User]:
    """Создает нового пользователя в базе данных.

    Args:
        db (Session): Сессия базы данных
        user_data (Dict): Данные пользователя:
            - user_id (int): ID пользователя ВКонтакте
            - first_name (str): Имя
            - last_name (str): Фамилия
            - age (Optional[int]): Возраст
            - gender (str): Пол ('male' или 'female')
            - city (Optional[str]): Город
            - access_token (Optional[str]): Токен доступа

    Returns:
        Optional[models.User]: Созданный пользователь или None при ошибке
    """
    try:
        db_user = models.User(
            user_id=user_data["user_id"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            age=user_data.get("age"),
            gender=user_data["gender"],
            city=user_data.get("city"),
            access_token=user_data.get("access_token"),
            state="main_menu"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка создания пользователя: {e}")
        return None


def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """Получает пользователя по ID ВКонтакте.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя ВКонтакте

    Returns:
        Optional[models.User]: Найденный пользователь или None
    """
    return db.query(models.User).filter(models.User.user_id == user_id).first()


def update_search_params(
    db: Session,
    user_id: int,
    interests: Optional[str] = None,
    **kwargs
) -> Optional[models.SearchParams]:
    """Обновляет параметры поиска пользователя.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        interests (Optional[str]): JSON-строка с интересами
        **kwargs: Дополнительные параметры:
            - min_age (int): Минимальный возраст
            - max_age (int): Максимальный возраст
            - gender (str): Пол ('male', 'female', 'any')
            - city (str): Город
            - has_photo (bool): Только с фото

    Returns:
        Optional[models.SearchParams]: Обновленные параметры или None при ошибке
    """
    try:
        params = db.query(models.SearchParams).filter_by(user_id=user_id).first()
        
        if not params:
            params = models.SearchParams(user_id=user_id, **kwargs)
            db.add(params)
        else:
            for key, value in kwargs.items():
                setattr(params, key, value)
        
        if interests is not None:
            params.interests = interests
            
        db.commit()
        return params
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка обновления параметров поиска: {e}")
        return None


def add_to_favorites(
    db: Session,
    user_id: int,
    favorite_user_id: int
) -> Optional[models.Favorite]:
    """Добавляет пользователя в избранное.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя, который добавляет
        favorite_user_id (int): ID добавляемого пользователя

    Returns:
        Optional[models.Favorite]: Созданная запись или None при ошибке
    """
    try:
        exists = db.query(models.Favorite).filter_by(
            user_id=user_id,
            favorite_user_id=favorite_user_id
        ).first()
        
        if exists:
            return exists
            
        fav = models.Favorite(
            user_id=user_id,
            favorite_user_id=favorite_user_id
        )
        db.add(fav)
        db.commit()
        return fav
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка добавления в избранное: {e}")
        return None


def remove_from_favorites(
    db: Session,
    user_id: int,
    favorite_user_id: int
) -> bool:
    """Удаляет пользователя из избранного.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        favorite_user_id (int): ID удаляемого пользователя

    Returns:
        bool: True если удаление прошло успешно, иначе False
    """
    try:
        fav = db.query(models.Favorite).filter_by(
            user_id=user_id,
            favorite_user_id=favorite_user_id
        ).first()
        
        if fav:
            db.delete(fav)
            db.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка удаления из избранного: {e}")
        return False


def add_to_blacklist(
    db: Session,
    user_id: int,
    blocked_user_id: int
) -> Optional[models.Blacklist]:
    """Добавляет пользователя в черный список.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        blocked_user_id (int): ID блокируемого пользователя

    Returns:
        Optional[models.Blacklist]: Созданная запись или None при ошибке
    """
    try:
        exists = db.query(models.Blacklist).filter_by(
            user_id=user_id,
            blocked_user_id=blocked_user_id
        ).first()
        
        if exists:
            return exists
            
        block = models.Blacklist(
            user_id=user_id,
            blocked_user_id=blocked_user_id
        )
        db.add(block)
        db.commit()
        return block
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка добавления в черный список: {e}")
        return None


def is_in_blacklist(
    db: Session,
    user_id: int,
    candidate_id: int
) -> bool:
    """Проверяет, находится ли пользователь в черном списке.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        candidate_id (int): ID проверяемого пользователя

    Returns:
        bool: True если пользователь в черном списке, иначе False
    """
    return db.query(models.Blacklist).filter_by(
        user_id=user_id,
        blocked_user_id=candidate_id
    ).first() is not None


def cache_match(
    db: Session,
    user_id: int,
    matched_user_id: int,
    photos: List[Dict],
    match_score: float = 0.0
) -> Optional[models.Match]:
    """Кэширует найденного кандидата.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        matched_user_id (int): ID найденного кандидата
        photos (List[Dict]): Список фотографий кандидата
        match_score (float): Оценка совпадения (по умолчанию 0.0)

    Returns:
        Optional[models.Match]: Созданная запись или None при ошибке
    """
    try:
        match = models.Match(
            user_id=user_id,
            matched_user_id=matched_user_id,
            photos=json.dumps(photos),
            match_score=match_score
        )
        db.add(match)
        db.commit()
        return match
    except (SQLAlchemyError, json.JSONDecodeError) as e:
        db.rollback()
        logger.error(f"Ошибка кэширования кандидата: {e}")
        return None


def get_favorites(db: Session, user_id: int) -> List[models.Favorite]:
    """Возвращает список избранных пользователей.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя

    Returns:
        List[models.Favorite]: Список избранных пользователей
    """
    return db.query(models.Favorite).filter_by(user_id=user_id).all()


def get_blacklist(db: Session, user_id: int) -> List[models.Blacklist]:
    """Возвращает черный список пользователя.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя

    Returns:
        List[models.Blacklist]: Список заблокированных пользователей
    """
    return db.query(models.Blacklist).filter_by(user_id=user_id).all()


def save_user_state(db: Session, user_id: int, state: BotState) -> bool:
    """Сохраняет состояние пользователя в базе данных.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        state (BotState): Состояние пользователя

    Returns:
        bool: True если сохранение прошло успешно, иначе False
    """
    if not isinstance(state, BotState):
        raise ValueError(f"Недопустимое состояние: {state}. Должно быть BotState enum")
    
    user = get_user(db, user_id)
    if user:
        user.state = state
        db.commit()
        return True
    return False


def get_user_state(db: Session, user_id: int) -> Optional[BotState]:
    """Получает текущее состояние пользователя.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя

    Returns:
        Optional[BotState]: Состояние пользователя или None
    """
    user = get_user(db, user_id)
    if user and user.state:
        try:
            return BotState(user.state)
        except ValueError:
            logger.error(f"Недопустимое состояние в БД: {user.state}")
            return None
    return None


def like_photo(
    db: Session,
    user_id: int,
    photo_owner_id: int,
    photo_id: int
) -> Optional[models.PhotoLike]:
    """Добавляет лайк фотографии.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        photo_owner_id (int): ID владельца фотографии
        photo_id (int): ID фотографии

    Returns:
        Optional[models.PhotoLike]: Созданная запись или None при ошибке
    """
    try:
        existing = db.query(models.PhotoLike).filter_by(
            user_id=user_id,
            photo_owner_id=photo_owner_id,
            photo_id=photo_id
        ).first()
        
        if existing:
            return existing
            
        like = models.PhotoLike(
            user_id=user_id,
            photo_owner_id=photo_owner_id,
            photo_id=photo_id
        )
        db.add(like)
        db.commit()
        return like
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка добавления лайка: {e}")
        return None


def unlike_photo(
    db: Session,
    user_id: int,
    photo_owner_id: int,
    photo_id: int
) -> bool:
    """Удаляет лайк фотографии.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        photo_owner_id (int): ID владельца фотографии
        photo_id (int): ID фотографии

    Returns:
        bool: True если удаление прошло успешно, иначе False
    """
    try:
        like = db.query(models.PhotoLike).filter_by(
            user_id=user_id,
            photo_owner_id=photo_owner_id,
            photo_id=photo_id
        ).first()
        
        if like:
            db.delete(like)
            db.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка удаления лайка: {e}")
        return False


def get_user_photo_likes(
    db: Session,
    user_id: int
) -> List[models.PhotoLike]:
    """Получает все лайки фотографий пользователя.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя

    Returns:
        List[models.PhotoLike]: Список лайков пользователя
    """
    return db.query(models.PhotoLike).filter_by(user_id=user_id).all()


def update_user_token(db: Session, user_id: int, token: str) -> bool:
    """Обновляет токен пользователя.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        token (str): Новый токен доступа

    Returns:
        bool: True если обновление прошло успешно, иначе False
    """
    try:
        user = db.query(models.User).filter(models.User.user_id == user_id).first()
        if user:
            user.access_token = token
            db.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка обновления токена: {e}")
        return False


def save_verifier(db: Session, user_id: int, verifier: str, state: str) -> bool:
    """Сохраняет code_verifier и state для аутентификации.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        verifier (str): Code verifier для OAuth
        state (str): Уникальный state для аутентификации

    Returns:
        bool: True если сохранение прошло успешно, иначе False
    """
    try:
        db.query(models.AuthState).filter(
            models.AuthState.user_id == user_id
        ).delete()
        
        new_state = models.AuthState(
            user_id=user_id,
            code_verifier=verifier,
            state=state,
            expires_at=datetime.now() + timedelta(minutes=10)
        )
        db.add(new_state)
        db.commit()
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка сохранения verifier: {e}")
        return False


def get_verifier(db: Session, user_id: int, state: str) -> Optional[str]:
    """Получает code_verifier по user_id и state.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        state (str): Уникальный state для аутентификации

    Returns:
        Optional[str]: Code verifier или None, если не найден
    """
    try:
        record = db.query(models.AuthState).filter(
            models.AuthState.user_id == user_id,
            models.AuthState.state == state,
            models.AuthState.expires_at > datetime.now()
        ).first()
        return record.code_verifier if record else None
    except SQLAlchemyError as e:
        logger.error(f"Ошибка получения verifier: {e}")
        return None


def get_search_params(db: Session, user_id: int) -> Optional[models.SearchParams]:
    """Получает параметры поиска для пользователя.

    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя

    Returns:
        Optional[models.SearchParams]: Параметры поиска или None
    """
    return db.query(models.SearchParams).filter(models.SearchParams.user_id == user_id).first()
    