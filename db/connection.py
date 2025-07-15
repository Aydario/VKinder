# Импортируем необходимые модули
from sqlalchemy import create_engine  # Для создания движка БД
from sqlalchemy.orm import sessionmaker  # Для создания сессий
from sqlalchemy.ext.declarative import declarative_base  # Для декларативной работы с моделями
from dotenv import load_dotenv  # Для загрузки переменных окружения
import os  # Для работы с системными переменными

# Загружаем переменные окружения из .env файла
load_dotenv()

# Формируем строку подключения к PostgreSQL из переменных окружения
DB_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:"  # Логин
    f"{os.getenv('POSTGRES_PASSWORD')}@"  # Пароль
    f"{os.getenv('POSTGRES_HOST')}:"  # Хост (обычно localhost)
    f"{os.getenv('POSTGRES_PORT')}/"  # Порт (обычно 5432)
    f"{os.getenv('POSTGRES_DB')}"  # Имя базы данных
)

# Создаем движок SQLAlchemy с параметрами:
# - pool_pre_ping=True - проверяет соединение перед использованием
engine = create_engine(DB_URL, pool_pre_ping=True)

# Создаем фабрику сессий с параметрами:
# - autocommit=False - отключаем автофиксацию
# - autoflush=False - отключаем автосброс
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей SQLAlchemy
Base = declarative_base()

# Генератор сессий для зависимостей FastAPI или других случаев
def get_db():
    db = SessionLocal()  # Создаем новую сессию
    try:
        yield db  # Возвращаем сессию для использования
    finally:
        db.close()  # Закрываем сессию в любом случае
