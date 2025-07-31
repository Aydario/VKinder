from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from typing import Optional
import json


def get_main_keyboard() -> Optional[dict]:
    """
    Создает клавиатуру главного меню.
    
    Возвращает:
        Optional[dict]: Клавиатура VK в формате JSON или None в случае ошибки
    """
    kb = VkKeyboard(one_time=False, inline=False)
    
    # Первая строка
    kb.add_button('🔍 Найти пару', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    
    # Вторая строка
    kb.add_button('⭐ Избранное', color=VkKeyboardColor.POSITIVE)
    kb.add_button('⚙️ Настройки', color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    
    # Третья строка
    kb.add_button('❌ Чёрный список', color=VkKeyboardColor.NEGATIVE)
    kb.add_button('ℹ️ Помощь', color=VkKeyboardColor.SECONDARY)
    
    return kb.get_keyboard()


def get_candidate_keyboard(has_liked: bool = False) -> Optional[dict]:
    """
    Создает клавиатуру для взаимодействия с профилем кандидата.
    
    Аргументы:
        has_liked (bool): Флаг, указывающий был ли уже поставлен лайк
        
    Возвращает:
        Optional[dict]: Клавиатура VK в формате JSON или None в случае ошибки
    """
    kb = VkKeyboard(inline=True)
    
    # Кнопки лайков
    if has_liked:
        kb.add_button('💔 Убрать лайк', color=VkKeyboardColor.SECONDARY)
    else:
        kb.add_button('❤️ Лайк', color=VkKeyboardColor.POSITIVE)
    
    # Основные действия
    kb.add_button('⭐ В избранное', color=VkKeyboardColor.POSITIVE)
    kb.add_button('✖️ В чёрный список', color=VkKeyboardColor.NEGATIVE)
    kb.add_line()
    
    # Навигация
    kb.add_button('➡️ Следующий', color=VkKeyboardColor.PRIMARY)
    kb.add_button('🏠 В меню', color=VkKeyboardColor.SECONDARY)
    
    return kb.get_keyboard()


def get_favorites_keyboard() -> Optional[dict]:
    """
    Создает клавиатуру для работы с избранными профилями.
    
    Возвращает:
        Optional[dict]: Клавиатура VK в формате JSON или None в случае ошибки
    """
    kb = VkKeyboard(inline=True)
    
    kb.add_button('👀 Посмотреть', color=VkKeyboardColor.PRIMARY)
    kb.add_button('🗑 Удалить', color=VkKeyboardColor.NEGATIVE)
    kb.add_line()
    kb.add_button('🔙 Назад', color=VkKeyboardColor.SECONDARY)
    
    return kb.get_keyboard()


def get_search_settings_keyboard() -> Optional[dict]:
    """
    Создает клавиатуру для настройки параметров поиска.
    
    Возвращает:
        Optional[dict]: Клавиатура VK в формате JSON или None в случае ошибки
    """
    kb = VkKeyboard(one_time=False)
    
    # Первая строка - возраст
    kb.add_button('👶 Возраст от', color=VkKeyboardColor.SECONDARY)
    kb.add_button('👴 Возраст до', color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    
    # Вторая строка - город и пол
    kb.add_button('🏙 Город', color=VkKeyboardColor.SECONDARY)
    kb.add_button('👫 Пол', color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    
    # Третья строка - приоритеты
    kb.add_button('📊 Приоритеты', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    
    # Четвертая строка - возврат
    kb.add_button('✅ Готово', color=VkKeyboardColor.POSITIVE)
    kb.add_button('🔙 Назад', color=VkKeyboardColor.SECONDARY)
    
    return kb.get_keyboard()


def get_priority_settings_keyboard() -> Optional[dict]:
    """
    Создает клавиатуру для настройки приоритетов при поиске.
    
    Возвращает:
        Optional[dict]: Клавиатура VK в формате JSON или None в случае ошибки
    """
    kb = VkKeyboard(one_time=False)
    
    kb.add_button('🔢 Возраст важнее', color=VkKeyboardColor.SECONDARY)
    kb.add_button('🎵 Музыка важнее', color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button('📚 Книги важнее', color=VkKeyboardColor.SECONDARY)
    kb.add_button('👥 Друзья важнее', color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button('🔙 Назад', color=VkKeyboardColor.SECONDARY)
    
    return kb.get_keyboard()


def get_confirm_keyboard() -> Optional[dict]:
    """
    Создает клавиатуру для подтверждения действий.
    
    Возвращает:
        Optional[dict]: Клавиатура VK в формате JSON или None в случае ошибки
    """
    kb = VkKeyboard(inline=True)
    
    kb.add_button('✅ Да', color=VkKeyboardColor.POSITIVE)
    kb.add_button('❌ Нет', color=VkKeyboardColor.NEGATIVE)
    
    return kb.get_keyboard()


def get_gender_keyboard() -> Optional[dict]:
    """
    Создает клавиатуру для выбора пола при поиске.
    
    Возвращает:
        Optional[dict]: Клавиатура VK в формате JSON или None в случае ошибки
    """
    kb = VkKeyboard(one_time=True)
    
    kb.add_button('👨 Мужской', color=VkKeyboardColor.PRIMARY)
    kb.add_button('👩 Женский', color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('👥 Любой', color=VkKeyboardColor.SECONDARY)
    
    return kb.get_keyboard()


def get_empty_keyboard() -> Optional[dict]:
    """
    Создает пустую клавиатуру (используется для скрытия предыдущей).
    
    Возвращает:
        Optional[dict]: Пустая клавиатура VK в формате JSON
    """
    return VkKeyboard.get_empty_keyboard()
    