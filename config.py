import os
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()


class Config:
    """
    Класс для работы с конфигурацией приложения.

    Содержит настройки для работы с API VK и базой данных.
    Все параметры загружаются из переменных окружения.
    """

    # Параметры для работы с VK API
    VK_GROUP_ID = os.getenv('VK_GROUP_ID')
    """ID группы VK, от имени которой работает бот"""
    
    VK_APP_ID = os.getenv('VK_APP_ID')
    """ID приложения VK"""
    
    VK_APP_SECRET = os.getenv('VK_APP_SECRET')
    """Секретный ключ приложения VK"""
    
    VK_GROUP_TOKEN = os.getenv('VK_GROUP_TOKEN')
    """Токен доступа группы VK"""
    
    VK_REDIRECT_URI = os.getenv("VK_REDIRECT_URI")
    """URI для перенаправления после авторизации"""
    
    VK_API_VERSION = os.getenv("VK_API_VERSION", "5.131")
    """Версия VK API (по умолчанию 5.131)"""

    # Параметры для подключения к базе данных
    DB_HOST = os.getenv('DB_HOST')
    """Хост базы данных"""
    
    DB_NAME = os.getenv('DB_NAME')
    """Имя базы данных"""
    
    DB_USER = os.getenv('DB_USER')
    """Пользователь базы данных"""
    
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    """Пароль для доступа к базе данных"""
    
    DB_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
    """URL для подключения к базе данных"""

    @staticmethod
    def update_env_var(key: str, value: str) -> None:
        """
        Обновляет переменную окружения в файле .env.

        Аргументы:
            key (str): Имя переменной для обновления
            value (str): Новое значение переменной

        Если переменная не существует, она будет добавлена в конец файла.
        """
        with open('.env', 'r+') as f:
            lines = f.readlines()
            f.seek(0)
            updated = False
            
            for line in lines:
                if line.startswith(f'{key}='):
                    f.write(f'{key}={value}\n')
                    updated = True
                else:
                    f.write(line)
            
            if not updated:
                f.write(f'{key}={value}\n')
            
            f.truncate()
