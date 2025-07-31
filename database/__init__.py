"""Модуль инициализации подключения к базе данных.

Содержит настройку движка SQLAlchemy, базового класса для моделей
и фабрики сессий для работы с БД.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import Config


# Настройка подключения к PostgreSQL с пулом соединений
engine = create_engine(
    Config.DB_URL,
    pool_size=10,       # Количество постоянных соединений в пуле
    max_overflow=20,    # Максимальное число временных соединений
    pool_pre_ping=True, # Проверка активности соединений перед использованием
    pool_recycle=3600   # Время жизни соединения (в секундах)
)

# Базовый класс для объявления моделей SQLAlchemy
Base = declarative_base()

# Фабрика для создания сессий работы с БД
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,    # Отключение автоматического сброса изменений
    expire_on_commit=False  # Отключение автоматического истечения сессии
)


def get_db():
    """Генератор сессий базы данных для использования в зависимостях.
    
    Yields:
        Session: Объект сессии SQLAlchemy
    
    Примечание:
        Автоматически закрывает соединение после завершения работы.
    
    Пример использования:
        db = next(get_db())
        try:
            # Работа с БД
        finally:
            db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        