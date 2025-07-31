import os
from dotenv import load_dotenv
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api import VkApi, exceptions
from utils.keyboard import (
    get_main_keyboard, 
    get_candidate_keyboard,
    get_favorites_keyboard,
    get_search_settings_keyboard,
    get_empty_keyboard,
    get_priority_settings_keyboard,
    get_gender_keyboard
)
from database import get_db
from database.crud import (
    get_user, 
    save_verifier, 
    get_verifier, 
    update_user_token, 
    save_user_state, 
    get_user_state, 
    create_user,
    get_favorites,
    remove_from_favorites,
    like_photo,
    unlike_photo,
    add_to_favorites,
    add_to_blacklist,
    get_search_params,
    update_search_params,
    get_blacklist
)
from vkapi.auth import generate_auth_link, extract_auth_params, get_access_token, generate_state, validate_token
from vkapi.methods import VKUserData, VKPhotos
from utils.matching import CandidateMatcher
from config import Config
import logging
from utils.states import BotState
from typing import Optional, Dict, List
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VKBot:
    """
    Основной класс бота для работы с VK API.
    
    Обрабатывает входящие сообщения, управляет состояниями пользователей
    и взаимодействует с базой данных.
    """

    def __init__(self):
        """Инициализация бота с загрузкой конфигурации"""
        self.config = Config()
        self.vk_session = None
        self.vk = None
        self.longpoll = None
        self.user_cache = {}  # Кэш данных пользователей {user_id: {data}}
        self._init_group_session()
        
    def _init_group_session(self):
        """
        Инициализация сессии для работы от имени группы VK.
        
        Вызывает исключение при ошибке инициализации.
        """
        try:
            self.vk_session = VkApi(token=self.config.VK_GROUP_TOKEN)
            self.vk = self.vk_session.get_api()
            self.longpoll = VkBotLongPoll(self.vk_session, group_id=self.config.VK_GROUP_ID)
        except Exception as e:
            logger.error(f"Ошибка инициализации сессии группы: {e}")
            raise

    def handle_auth_flow(self, user_id: int, text: str) -> Optional[str]:
        """
        Обработка потока авторизации пользователя.
        
        Args:
            user_id: ID пользователя VK
            text: Текст сообщения от пользователя
            
        Returns:
            Optional[str]: Сообщение для отправки пользователю или None, если авторизация завершена
        """
        text = text.strip()
        db = next(get_db())

        if text.lower() == "авторизоваться":
            state = generate_state()
            auth_url, verifier = generate_auth_link(state)
            
            if not save_verifier(db, user_id, verifier, state):
                return "Ошибка при подготовке авторизации"

            # Создаём или обновляем пользователя
            user = get_user(db, user_id)
            if not user:
                try:
                    user_info = self.vk.users.get(
                        user_ids=user_id,
                        fields="first_name,last_name,sex,city"
                    )[0]
                    
                    user_data = {
                        "user_id": user_id,
                        "first_name": user_info.get('first_name', ''),
                        "last_name": user_info.get('last_name', ''),
                        "gender": "female" if user_info.get('sex') == 1 else "male",
                        "city": user_info.get('city', {}).get('title') if isinstance(user_info.get('city'), dict) else None,
                        "state": BotState.AUTH_IN_PROGRESS.value
                    }
                    create_user(db, user_data)
                except Exception as e:
                    logger.error(f"Ошибка создания пользователя: {e}")
                    return "Ошибка при создании профиля"

            save_user_state(db, user_id, BotState.MAIN_MENU)

            return f"""Для работы бота необходимо предоставить доступ к вашему профилю VK.
Пожалуйста, перейдите по ссылке для авторизации:
{auth_url}

Далее нажмите на 'Разрешить', после перехода на другую страницу, скопируйте адрес и отправьте боту."""

        elif "code=" in text:
            params = extract_auth_params(text)
            if not params:
                return "Неверные параметры авторизации"

            verifier = get_verifier(db, user_id, params["state"])
            if not verifier:
                return "Сессия устарела, начните заново"

            token, vk_id = get_access_token(
                code=params["code"],
                code_verifier=verifier,
                state=params["state"],
                device_id=params["device_id"]
            )

            if not token or not vk_id:
                return "Ошибка получения токена"

            # Обязательно создаём пользователя, если не существует
            user = get_user(db, user_id)
            if not user:
                try:
                    user_info = self.vk.users.get(user_ids=user_id, fields="first_name,last_name")[0]
                    user_data = {
                        "user_id": user_id,
                        "first_name": user_info.get('first_name', ''),
                        "last_name": user_info.get('last_name', ''),
                        "state": BotState.MAIN_MENU.value
                    }
                    create_user(db, user_data)
                except Exception as e:
                    logger.error(f"Ошибка создания пользователя: {e}")
                    return "Ошибка создания профиля"

            update_user_token(db, user_id, token)
            save_user_state(db, user_id, BotState.MAIN_MENU)
            
            # Отправляем сообщение с клавиатурой
            self.vk.messages.send(
                user_id=user_id,
                message="✅ Авторизация успешна! Используйте меню:",
                keyboard=get_main_keyboard(),
                random_id=0
            )
            return None 

        return None

    def start_search(self, user_id: int):
        """
        Начинает поиск кандидатов и показывает первого подходящего.
        
        Args:
            user_id: ID пользователя, для которого выполняется поиск
        """
        try:
            db = next(get_db())
            save_user_state(db, user_id, BotState.SEARCHING)
            
            user = get_user(db, user_id)
            if not user or not user.access_token or not validate_token(user.access_token):
                self.vk.messages.send(
                    user_id=user_id,
                    message="❌ Требуется повторная авторизация. Напишите 'авторизоваться'",
                    random_id=0
                )
                return
            
            if not get_search_params(db, user_id):
                self._init_default_search_params(user_id)

            matcher = CandidateMatcher(db, user_id, user.access_token)
            
            try:
                candidate = matcher.get_next_candidate()
            except exceptions.ApiError as e:
                if e.code == 9:  # Flood control
                    self.vk.messages.send(
                        user_id=user_id,
                        message="⏳ Слишком много запросов. Подождите 10 секунд...",
                        random_id=0
                    )
                    time.sleep(10)  # Ждём 10 секунд и пробуем снова
                    candidate = matcher.get_next_candidate()
                else:
                    raise e  # Если другая ошибка - пробрасываем дальше
            
            if not candidate:
                self.vk.messages.send(
                    user_id=user_id,
                    message="😔 Не удалось найти подходящих кандидатов. Попробуйте изменить параметры поиска.",
                    keyboard=get_main_keyboard(),
                    random_id=0
                )
                save_user_state(db, user_id, BotState.MAIN_MENU)
                return
            
            self.user_cache[user_id] = {'current_candidate': candidate}
            self.show_candidate(user_id, candidate)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            self.vk.messages.send(
                user_id=user_id,
                message="⚠️ Ошибка при поиске. Попробуйте изменить параметры.",
                random_id=0
            )

    def show_candidate(self, user_id: int, candidate: dict):
        """
        Отображает профиль кандидата пользователю.
        
        Args:
            user_id: ID пользователя, которому показываем кандидата
            candidate: Данные кандидата
        """
        db = next(get_db())
        save_user_state(db, user_id, BotState.VIEWING_CANDIDATE)
        
        # Проверяем лайки
        has_liked = False  # Здесь можно добавить проверку из БД
        
        # Формируем сообщение
        message = (
            f"👤 {candidate.get('first_name', '')} {candidate.get('last_name', '')}\n"
            f"🔗 Профиль: vk.com/{candidate.get('domain', '')}\n"
            f"💯 Совпадение: {candidate.get('match_score', 0)*100:.0f}%"
        )
        
        # Формируем вложения для фото
        attachments = None
        if candidate.get('photos'):
            photo_attachments = []
            for photo in candidate['photos']:
                photo_attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
            attachments = ",".join(photo_attachments)
        
        # Отправляем сообщение
        self.vk.messages.send(
            user_id=user_id,
            message=message,
            keyboard=get_candidate_keyboard(has_liked),
            attachment=attachments,
            random_id=0
        )

    def show_favorites(self, user_id: int):
        """
        Отображает список избранных кандидатов.
        
        Args:
            user_id: ID пользователя
        """
        try:
            db = next(get_db())
            save_user_state(db, user_id, BotState.FAVORITES)
            
            favorites = get_favorites(db, user_id)
            if not favorites:
                self.vk.messages.send(
                    user_id=user_id,
                    message="⭐ Ваш список избранных пуст",
                    keyboard=get_main_keyboard(),
                    random_id=0
                )
                save_user_state(db, user_id, BotState.MAIN_MENU)
                return
            
            # Формируем список избранных
            message = "⭐ Ваши избранные:\n\n"
            for i, fav in enumerate(favorites[:10], 1):
                message += f"{i}. id{fav.favorite_user_id}\n"
            
            # Сохраняем избранных в кэш
            if user_id not in self.user_cache:
                self.user_cache[user_id] = {}
            self.user_cache[user_id]['favorites'] = [f.favorite_user_id for f in favorites]
            
            self.vk.messages.send(
                user_id=user_id,
                message=message,
                keyboard=get_favorites_keyboard(),
                random_id=0
            )
            
        except Exception as e:
            logger.error(f"Ошибка при показе избранных: {e}")
            self.vk.messages.send(
                user_id=user_id,
                message="⚠️ Произошла ошибка при загрузке избранных",
                random_id=0
            )

    def remove_favorite(self, user_id: int, index: int):
        """
        Удаляет кандидата из избранного по индексу.
        
        Args:
            user_id: ID пользователя
            index: Порядковый номер в списке избранных
        """
        try:
            db = next(get_db())
            if user_id not in self.user_cache or 'favorites' not in self.user_cache[user_id]:
                self.show_favorites(user_id)
                return
            
            favorites = self.user_cache[user_id]['favorites']
            if index < 1 or index > len(favorites):
                self.vk.messages.send(
                    user_id=user_id,
                    message="❌ Неверный номер избранного",
                    random_id=0
                )
                return
            
            favorite_id = favorites[index-1]
            if remove_from_favorites(db, user_id, favorite_id):
                self.vk.messages.send(
                    user_id=user_id,
                    message=f"❌ Пользователь id{favorite_id} удален из избранных",
                    random_id=0
                )
            else:
                self.vk.messages.send(
                    user_id=user_id,
                    message=f"⚠️ Не удалось удалить пользователя id{favorite_id}",
                    random_id=0
                )
            
            # Обновляем список
            self.show_favorites(user_id)
            
        except Exception as e:
            logger.error(f"Ошибка при удалении из избранных: {e}")
            self.vk.messages.send(
                user_id=user_id,
                message="⚠️ Произошла ошибка при удалении",
                random_id=0
            )

    def like_candidate_photos(self, user_id: int, candidate_id: int):
        """
        Ставит лайки на лучшие фото кандидата.
        
        Args:
            user_id: ID пользователя
            candidate_id: ID кандидата
        """
        candidate = self.user_cache.get(user_id, {}).get('current_candidate')
        if not candidate or not candidate.get('photos'):
            return
            
        db = next(get_db())
        liked = False
        
        for photo in candidate['photos'][:3]:
            if like_photo(db, user_id, photo['owner_id'], photo['id']):
                liked = True
        
        if liked:
            self.vk.messages.send(
                user_id=user_id,
                message="❤️ Лайки поставлены на лучшие фотографии!",
                keyboard=get_candidate_keyboard(True),
                random_id=0
            )

    def unlike_candidate_photos(self, user_id: int, candidate_id: int):
        """
        Убирает лайки с фото кандидата.
        
        Args:
            user_id: ID пользователя
            candidate_id: ID кандидата
        """
        candidate = self.user_cache.get(user_id, {}).get('current_candidate')
        if not candidate or not candidate.get('photos'):
            return
            
        db = next(get_db())
        unliked = False
        
        for photo in candidate['photos'][:3]:
            if unlike_photo(db, user_id, photo['owner_id'], photo['id']):
                unliked = True
        
        if unliked:
            self.vk.messages.send(
                user_id=user_id,
                message="💔 Лайки убраны с фотографий",
                keyboard=get_candidate_keyboard(False),
                random_id=0
            )

    def add_to_favorites(self, user_id: int, candidate_id: int):
        """
        Добавляет кандидата в избранное.
        
        Args:
            user_id: ID пользователя
            candidate_id: ID кандидата
        """
        db = next(get_db())
        if add_to_favorites(db, user_id, candidate_id):
            self.vk.messages.send(
                user_id=user_id,
                message="⭐ Пользователь добавлен в избранное!",
                random_id=0
            )
        else:
            self.vk.messages.send(
                user_id=user_id,
                message="⚠️ Не удалось добавить в избранное",
                random_id=0
            )

    def add_to_blacklist(self, user_id: int, candidate_id: int):
        """
        Добавляет кандидата в черный список.
        
        Args:
            user_id: ID пользователя
            candidate_id: ID кандидата
        """
        db = next(get_db())
        if add_to_blacklist(db, user_id, candidate_id):
            self.vk.messages.send(
                user_id=user_id,
                message="🚫 Пользователь добавлен в черный список",
                random_id=0
            )
            # Переходим к следующему
            self.start_search(user_id)
        else:
            self.vk.messages.send(
                user_id=user_id,
                message="⚠️ Не удалось добавить в черный список",
                random_id=0
            )

    def show_search_settings(self, user_id: int):
        """
        Отображает текущие настройки поиска.
        
        Args:
            user_id: ID пользователя
        """
        try:
            db = next(get_db())
            save_user_state(db, user_id, BotState.SEARCH_SETTINGS)
            
            params = get_search_params(db, user_id)
            if not params:
                self._init_default_search_params(user_id)
                params = get_search_params(db, user_id)
            
            message = (
                "🔧 Текущие настройки поиска:\n\n"
                f"• Возраст: от {params.min_age} до {params.max_age}\n"
                f"• Пол: {params.gender}\n"
                f"• Город: {params.city or 'не указан'}\n"
                f"• Только с фото: {'да' if params.has_photo else 'нет'}"
            )
            
            self.vk.messages.send(
                user_id=user_id,
                message=message,
                keyboard=get_search_settings_keyboard(),
                random_id=0
            )
            
        except Exception as e:
            logger.error(f"Ошибка при показе настроек: {e}")
            self.vk.messages.send(
                user_id=user_id,
                message="⚠️ Произошла ошибка при загрузке настроек",
                random_id=0
            )

    def _init_default_search_params(self, user_id: int):
        """
        Инициализирует параметры поиска по умолчанию.
        
        Args:
            user_id: ID пользователя
        """
        db = next(get_db())
        user = get_user(db, user_id)
        if not user:
            return
            
        default_params = {
            "min_age": max(18, (user.age or 25) - 5),
            "max_age": (user.age or 25) + 5,
            "gender": "female" if user.gender == "male" else "male",
            "city": user.city,
            "has_photo": True
        }
        
        update_search_params(db, user_id, **default_params)

    def _ask_min_age(self, user_id: int):
        """
        Запрашивает минимальный возраст для поиска.
        
        Args:
            user_id: ID пользователя
        """
        db = next(get_db())
        save_user_state(db, user_id, BotState.AWAITING_MIN_AGE)
        self.vk.messages.send(
            user_id=user_id,
            message="Введите минимальный возраст для поиска (от 18):",
            keyboard=get_empty_keyboard(),
            random_id=0
        )

    def _ask_max_age(self, user_id: int):
        """
        Запрашивает максимальный возраст для поиска.
        
        Args:
            user_id: ID пользователя
        """
        db = next(get_db())
        save_user_state(db, user_id, BotState.AWAITING_MAX_AGE)
        self.vk.messages.send(
            user_id=user_id,
            message="Введите максимальный возраст для поиска (до 99):",
            keyboard=get_empty_keyboard(),
            random_id=0
        )

    def _ask_city(self, user_id: int):
        """
        Запрашивает город для поиска.
        
        Args:
            user_id: ID пользователя
        """
        db = next(get_db())
        save_user_state(db, user_id, BotState.AWAITING_CITY)
        self.vk.messages.send(
            user_id=user_id,
            message="Введите город для поиска:",
            keyboard=get_empty_keyboard(),
            random_id=0
        )

    def handle_message(self, user_id: int, text: str):
        """
        Основной обработчик входящих сообщений.
        
        Args:
            user_id: ID пользователя
            text: Текст сообщения
        """
        db = next(get_db())
        state = get_user_state(db, user_id)
        
        # Обработка команд вне зависимости от состояния
        if text.lower() in ['меню', 'начать', 'старт']:
            self._show_main_menu(user_id)
            return
        
        # Обработка состояний ввода данных
        if state == BotState.AWAITING_MIN_AGE:
            self._process_age_input(user_id, text, 'min')
            save_user_state(db, user_id, BotState.SEARCH_SETTINGS)
            return
        elif state == BotState.AWAITING_MAX_AGE:
            self._process_age_input(user_id, text, 'max')
            save_user_state(db, user_id, BotState.SEARCH_SETTINGS)
            return
        elif state == BotState.AWAITING_CITY:
            self._process_city_input(user_id, text)
            save_user_state(db, user_id, BotState.SEARCH_SETTINGS)
            return
        
        # Обработка по состояниям
        if state == BotState.MAIN_MENU:
            self._handle_main_menu(user_id, text)
        elif state == BotState.VIEWING_CANDIDATE:
            self._handle_candidate_actions(user_id, text)
        elif state == BotState.FAVORITES:
            self._handle_favorites_actions(user_id, text)
        elif state == BotState.SEARCH_SETTINGS:
            self._handle_settings_actions(user_id, text)
        elif state == BotState.PRIORITY_SETTINGS:
            if text == '🔙 Назад':
                self.show_search_settings(user_id)
            else:
                self._process_priority_selection(user_id, text)
        else:
            self._show_main_menu(user_id)

    def _handle_main_menu(self, user_id: int, text: str):
        """
        Обработчик действий в главном меню.
        
        Args:
            user_id: ID пользователя
            text: Текст сообщения
        """
        if text == '🔍 Найти пару':
            self.start_search(user_id)
        elif text == '⭐ Избранное':
            self.show_favorites(user_id)
        elif text == '⚙️ Настройки':
            self.show_search_settings(user_id)
        elif text == '❌ Чёрный список':
            self.show_blacklist(user_id)
        elif text == 'ℹ️ Помощь':
            self.show_help(user_id)
        else:
            self.vk.messages.send(
                user_id=user_id,
                message="ℹ️ Используйте кнопки меню",
                random_id=0
            )

    def _handle_candidate_actions(self, user_id: int, text: str):
        """
        Обработчик действий при просмотре кандидата.
        
        Args:
            user_id: ID пользователя
            text: Текст сообщения
        """
        candidate = self.user_cache.get(user_id, {}).get('current_candidate')
        if not candidate:
            self.start_search(user_id)
            return
            
        if text == '❤️ Лайк':
            self.like_candidate_photos(user_id, candidate['id'])
        elif text == '💔 Убрать лайк':
            self.unlike_candidate_photos(user_id, candidate['id'])
        elif text == '⭐ В избранное':
            self.add_to_favorites(user_id, candidate['id'])
        elif text == '✖️ В чёрный список':
            self.add_to_blacklist(user_id, candidate['id'])
        elif text == '➡️ Следующий':
            self.start_search(user_id)
        elif text == '🏠 В меню':
            self._show_main_menu(user_id)
        else:
            self.vk.messages.send(
                user_id=user_id,
                message="ℹ️ Используйте кнопки для взаимодействия с кандидатом",
                random_id=0
            )

    def _handle_favorites_actions(self, user_id: int, text: str):
        """
        Обработчик действий с избранным.
        
        Args:
            user_id: ID пользователя
            text: Текст сообщения
        """
        if text == '👀 Посмотреть':
            self.view_favorite(user_id)
        elif text == '🗑 Удалить':
            self.ask_favorite_to_remove(user_id)
        elif text == '🔙 Назад':
            self._show_main_menu(user_id)
        else:
            # Попытка удалить по номеру
            if text.isdigit():
                self.remove_favorite(user_id, int(text))
            else:
                self.vk.messages.send(
                    user_id=user_id,
                    message="ℹ️ Используйте кнопки или номер для удаления",
                    random_id=0
                )

    def _handle_settings_actions(self, user_id: int, text: str):
        """
        Обработчик действий в настройках.
        
        Args:
            user_id: ID пользователя
            text: Текст сообщения
        """
        if text == '👶 Возраст от':
            self._ask_min_age(user_id)
        elif text == '👴 Возраст до':
            self._ask_max_age(user_id)
        elif text == '🏙 Город':
            self._ask_city(user_id)
        elif text == '👫 Пол':
            self._ask_gender(user_id)
        elif text == '📊 Приоритеты':
            self._show_priority_settings(user_id)
        elif text == '✅ Готово':
            self._show_main_menu(user_id)
        elif text == '🔙 Назад':
            self._show_main_menu(user_id)
        else:
            self.vk.messages.send(
                user_id=user_id,
                message="ℹ️ Используйте кнопки для изменения настроек",
                random_id=0
            )

    def _show_main_menu(self, user_id: int):
        """
        Отображает главное меню.
        
        Args:
            user_id: ID пользователя
        """
        db = next(get_db())
        save_user_state(db, user_id, BotState.MAIN_MENU)
        self.vk.messages.send(
            user_id=user_id,
            message="Главное меню:",
            keyboard=get_main_keyboard(),
            random_id=0
        )

    def _process_age_input(self, user_id: int, text: str, age_type: str):
        """
        Обрабатывает ввод возраста.
        
        Args:
            user_id: ID пользователя
            text: Введенный текст
            age_type: Тип возраста ('min' или 'max')
        """
        try:
            age = int(text)
            if age_type == 'min' and (age < 18 or age > 99):
                raise ValueError("Возраст должен быть от 18 до 99")
            elif age_type == 'max' and (age < 18 or age > 99):
                raise ValueError("Возраст должен быть от 18 до 99")
                
            update_search_params(next(get_db()), user_id, **{f"{age_type}_age": age})
            self.show_search_settings(user_id)  # Возвращаем в меню настроек
            
        except ValueError as e:
            self.vk.messages.send(
                user_id=user_id,
                message=f"❌ {str(e)}. Попробуйте еще раз:",
                keyboard=get_empty_keyboard(),
                random_id=0
            )
            # Остаемся в состоянии ожидания ввода
            save_user_state(next(get_db()), user_id, 
                        BotState.AWAITING_MIN_AGE if age_type == 'min' 
                        else BotState.AWAITING_MAX_AGE)

    def _process_city_input(self, user_id: int, text: str):
        """
        Обрабатывает ввод города.
        
        Args:
            user_id: ID пользователя
            text: Введенный текст
        """
        db = next(get_db())
        try:
            update_search_params(db, user_id, city=text)
            self.show_search_settings(user_id)  # Возвращаем в меню настроек
        except Exception as e:
            logger.error(f"Error setting city: {e}")
            self.vk.messages.send(
                user_id=user_id,
                message="❌ Ошибка при сохранении города. Попробуйте еще раз:",
                keyboard=get_empty_keyboard(),
                random_id=0
            )
            save_user_state(db, user_id, BotState.AWAITING_CITY)

    def _process_gender_selection(self, user_id: int, text: str):
        """
        Обрабатывает выбор пола.
        
        Args:
            user_id: ID пользователя
            text: Выбранный вариант пола
        """
        gender_map = {
            '👨 Мужской': 'male',
            '👩 Женский': 'female',
            '👥 Любой': 'any'
        }
        
        if text in gender_map:
            update_search_params(next(get_db()), user_id, gender=gender_map[text])
            self.vk.messages.send(
                user_id=user_id,
                message=f"✅ Пол для поиска установлен: {text}",
                keyboard=get_search_settings_keyboard(),
                random_id=0
            )
        else:
            self.vk.messages.send(
                user_id=user_id,
                message="❌ Неверный выбор пола",
                random_id=0
            )

    def _process_priority_selection(self, user_id: int, text: str):
        """
        Обрабатывает выбор приоритетов.
        
        Args:
            user_id: ID пользователя
            text: Выбранный вариант приоритета
        """
        priority_map = {
            '🔢 Возраст важнее': {'age_weight': 1.0, 'interests_weight': 0.7},
            '🎵 Музыка важнее': {'interests_weight': 1.0, 'age_weight': 0.7},
            '📚 Книги важнее': {'interests_weight': 1.0, 'age_weight': 0.7},
            '👥 Друзья важнее': {'friends_weight': 1.0, 'age_weight': 0.7}
        }
        
        if text in priority_map:
            update_search_params(next(get_db()), user_id, **priority_map[text])
            self.vk.messages.send(
                user_id=user_id,
                message=f"✅ Приоритет установлен: {text}",
                keyboard=get_priority_settings_keyboard(),
                random_id=0
            )
        else:
            self.vk.messages.send(
                user_id=user_id,
                message="❌ Неверный выбор приоритета",
                random_id=0
            )

    def show_blacklist(self, user_id: int):
        """
        Отображает черный список пользователя.
        
        Args:
            user_id: ID пользователя
        """
        try:
            db = next(get_db())
            blacklist = get_blacklist(db, user_id)
            
            if not blacklist:
                message = "Ваш черный список пуст"
            else:
                message = "🚫 Ваш черный список:\n" + "\n".join(
                    [f"{i+1}. id{user.blocked_user_id}" for i, user in enumerate(blacklist)]
                )
                
            self.vk.messages.send(
                user_id=user_id,
                message=message,
                keyboard=get_main_keyboard(),
                random_id=0
            )
        except Exception as e:
            logger.error(f"Error showing blacklist: {e}")
            self.vk.messages.send(
                user_id=user_id,
                message="⚠️ Ошибка при загрузке черного списка",
                random_id=0
            )

    def show_help(self, user_id: int):
        """
        Отображает справку по боту.
        
        Args:
            user_id: ID пользователя
        """
        help_text = """
        ℹ️ Помощь по боту:
        
        🔍 Найти пару - начать поиск
        ⭐ Избранное - ваши сохраненные анкеты
        ⚙️ Настройки - параметры поиска
        ❌ Чёрный список - заблокированные пользователи
        
        В настройках вы можете указать:
        - Возрастной диапазон
        - Город
        - Пол
        - Приоритеты поиска
        """
        self.vk.messages.send(
            user_id=user_id,
            message=help_text,
            keyboard=get_main_keyboard(),
            random_id=0
        )

    def run(self):
        """
        Основной цикл работы бота.
        
        Обрабатывает входящие события от VK LongPoll API.
        """
        logger.info("Бот запущен и ожидает сообщений...")
        
        while True:
            try:
                for event in self.longpoll.listen():
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        user_id = event.obj.message['from_id']
                        text = event.obj.message['text']
                        
                        # Обработка авторизации
                        auth_response = self.handle_auth_flow(user_id, text)
                        if auth_response:
                            self.vk.messages.send(
                                user_id=user_id,
                                message=auth_response,
                                random_id=0
                            )
                            continue
                            
                        # Проверяем авторизацию пользователя
                        db = next(get_db())
                        user = get_user(db, user_id)
                        
                        if not user or not user.access_token:
                            self.vk.messages.send(
                                user_id=user_id,
                                message="🔒 Для работы бота необходимо авторизоваться. Напишите 'авторизоваться'",
                                random_id=0
                            )
                            continue
                            
                        # Обрабатываем сообщение
                        self.handle_message(user_id, text)
                        
            except Exception as e:
                logger.error(f"Ошибка в основном цикле бота: {e}")
                if "connection" in str(e).lower():
                    self._init_group_session()


if __name__ == "__main__":
    bot = VKBot()
    bot.run()
