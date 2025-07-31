from enum import Enum, auto


class BotState(str, Enum):
    """
    Перечисление состояний бота.
    
    Каждое состояние соответствует определенному экрану или этапу взаимодействия с пользователем.
    Наследуется от str для удобной сериализации/десериализации.
    """
    
    MAIN_MENU = "MAIN_MENU"
    """Главное меню бота"""
    
    SEARCHING = "SEARCHING"
    """Состояние поиска кандидатов"""
    
    VIEWING_CANDIDATE = "VIEWING_CANDIDATE"
    """Просмотр профиля конкретного кандидата"""
    
    FAVORITES = "FAVORITES"
    """Работа с избранными кандидатами"""
    
    SEARCH_SETTINGS = "SEARCH_SETTINGS"
    """Настройки параметров поиска"""
    
    PRIORITY_SETTINGS = "PRIORITY_SETTINGS"
    """Настройка приоритетов при поиске"""
    
    AUTH_IN_PROGRESS = "AUTH_IN_PROGRESS"
    """Процесс авторизации пользователя"""
    
    AWAITING_MIN_AGE = "AWAITING_MIN_AGE"
    """Ожидание ввода минимального возраста для поиска"""
    
    AWAITING_MAX_AGE = "AWAITING_MAX_AGE"
    """Ожидание ввода максимального возраста для поиска"""
    
    AWAITING_CITY = "AWAITING_CITY"
    """Ожидание ввода города для поиска"""
    