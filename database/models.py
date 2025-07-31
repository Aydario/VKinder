"""Модуль моделей базы данных для бота знакомств.

Содержит все модели SQLAlchemy, используемые в проекте.
"""

from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, JSON, Float, DateTime
from sqlalchemy.sql import func
from database import Base
from sqlalchemy import Enum as SqlEnum 
from utils.states import BotState


class User(Base):
    """Модель пользователя ВКонтакте.

    Attributes:
        user_id (int): Уникальный идентификатор пользователя ВКонтакте (первичный ключ)
        first_name (str): Имя пользователя (обязательное поле)
        last_name (str): Фамилия пользователя
        age (int): Возраст пользователя
        gender (str): Пол пользователя ('male' или 'female')
        city (str): Город пользователя
        access_token (str): Токен доступа к API ВКонтакте
        registration_date (datetime): Дата и время регистрации (автоматически устанавливается)
        state (BotState): Текущее состояние пользователя в боте
    """

    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    age = Column(Integer)
    gender = Column(String(10))
    city = Column(String(100))
    access_token = Column(String(500))
    registration_date = Column(TIMESTAMP, server_default=func.now())
    state = Column(
        SqlEnum(BotState, name='bot_state'),
        default=BotState.MAIN_MENU,
        nullable=False
    )


class SearchParams(Base):
    """Модель параметров поиска для пользователя.

    Attributes:
        param_id (int): Уникальный идентификатор параметров (автоинкремент)
        user_id (int): Идентификатор пользователя (внешний ключ)
        min_age (int): Минимальный возраст для поиска (по умолчанию 18)
        max_age (int): Максимальный возраст для поиска (по умолчанию 45)
        gender (str): Пол для поиска ('male', 'female' или 'any')
        city (str): Город для поиска
        has_photo (bool): Флаг поиска только пользователей с фото (по умолчанию True)
        interests (str): JSON-строка с интересами для поиска
        age_weight (float): Вес критерия возраста при поиске (по умолчанию 1.0)
        interests_weight (float): Вес критерия интересов (по умолчанию 0.7)
        groups_weight (float): Вес критерия общих групп (по умолчанию 0.5)
        friends_weight (float): Вес критерия общих друзей (по умолчанию 0.8)
    """

    __tablename__ = 'search_params'
    
    param_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), unique=True)
    min_age = Column(Integer, default=18)
    max_age = Column(Integer, default=45)
    gender = Column(String(10))
    city = Column(String(100))
    has_photo = Column(Boolean, default=True)
    interests = Column(String(500))

    age_weight = Column(Float, default=1.0)
    interests_weight = Column(Float, default=0.7)
    groups_weight = Column(Float, default=0.5)
    friends_weight = Column(Float, default=0.8)


class Favorite(Base):
    """Модель избранных анкет.

    Attributes:
        favorite_id (int): Уникальный идентификатор записи (автоинкремент)
        user_id (int): Идентификатор пользователя, добавившего в избранное (внешний ключ)
        favorite_user_id (int): Идентификатор пользователя в избранном
        added_at (datetime): Дата и время добавления (автоматически устанавливается)
    """

    __tablename__ = 'favorites'
    
    favorite_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    favorite_user_id = Column(Integer)
    added_at = Column(TIMESTAMP, server_default=func.now())


class Blacklist(Base):
    """Модель черного списка пользователей.

    Attributes:
        block_id (int): Уникальный идентификатор блокировки (автоинкремент)
        user_id (int): Идентификатор пользователя, добавившего в ЧС (внешний ключ)
        blocked_user_id (int): Идентификатор заблокированного пользователя
        blocked_at (datetime): Дата и время блокировки (автоматически устанавливается)
    """

    __tablename__ = 'blacklist'
    
    block_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    blocked_user_id = Column(Integer)
    blocked_at = Column(TIMESTAMP, server_default=func.now())


class Match(Base):
    """Модель кэширования найденных кандидатов.

    Attributes:
        match_id (int): Уникальный идентификатор совпадения (автоинкремент)
        user_id (int): Идентификатор пользователя, для которого найден кандидат (внешний ключ)
        matched_user_id (int): Идентификатор найденного кандидата
        match_score (float): Оценка совпадения (от 0.0 до 1.0)
        photos (JSON): Список фотографий кандидата в формате JSON
        last_shown (datetime): Дата и время последнего показа кандидата
    """

    __tablename__ = 'matches'
    
    match_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    matched_user_id = Column(Integer)
    match_score = Column(Float)
    photos = Column(JSON)
    last_shown = Column(TIMESTAMP)


class AuthState(Base):
    """Модель для хранения состояния аутентификации.

    Attributes:
        id (int): Уникальный идентификатор записи (автоинкремент)
        user_id (int): Идентификатор пользователя
        code_verifier (str): Уникальный код верификации для OAuth
        state (str): Уникальный идентификатор состояния
        expires_at (datetime): Время истечения срока действия записи
    """

    __tablename__ = 'auth_states'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    code_verifier = Column(String(128), nullable=False)
    state = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)


class PhotoLike(Base):
    """Модель лайков фотографий.

    Attributes:
        like_id (int): Уникальный идентификатор лайка (автоинкремент)
        user_id (int): Идентификатор пользователя, поставившего лайк (внешний ключ)
        photo_owner_id (int): Идентификатор владельца фотографии
        photo_id (int): Идентификатор фотографии
        liked_at (datetime): Дата и время установки лайка (автоматически устанавливается)
    """

    __tablename__ = 'photo_likes'
    
    like_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    photo_owner_id = Column(Integer)
    photo_id = Column(Integer)
    liked_at = Column(TIMESTAMP, server_default=func.now())
    