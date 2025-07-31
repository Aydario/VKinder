"""Модуль для работы с OAuth аутентификацией ВКонтакте.

Содержит функции для генерации ссылок аутентификации, обработки OAuth flow
и работы с access token.
"""

import requests
import secrets
import hashlib
import base64
from urllib.parse import parse_qs, urlparse, urlencode
from typing import Optional, Tuple, Dict
from config import Config
import time
import logging


def generate_state() -> str:
    """Генерирует уникальный state параметр для OAuth аутентификации.

    Returns:
        str: Случайно сгенерированная строка state длиной 32 символа
    """
    return secrets.token_urlsafe(32)


def generate_code_verifier(length: int = 64) -> str:
    """Генерирует code_verifier для PKCE (Proof Key for Code Exchange).

    Args:
        length (int): Длина code_verifier (по умолчанию 64)

    Returns:
        str: Сгенерированный code_verifier
    """
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_code_challenge(verifier: str) -> str:
    """Создает code_challenge из verifier для PKCE.

    Args:
        verifier (str): code_verifier

    Returns:
        str: code_challenge в формате base64url
    """
    sha256 = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(sha256).decode().rstrip("=")


def generate_auth_link(state: str) -> Tuple[str, str]:
    """Генерирует URL для аутентификации через VK ID с PKCE.

    Args:
        state (str): Уникальный параметр state

    Returns:
        Tuple[str, str]: (URL для аутентификации, code_verifier)
    """
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    params = {
        "client_id": Config.VK_APP_ID,
        "redirect_uri": Config.VK_REDIRECT_URI,
        "response_type": "code",
        "scope": "friends,photos,groups,wall",
        "v": Config.VK_API_VERSION,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state
    }

    return f"https://id.vk.com/authorize?{urlencode(params)}", code_verifier


def get_access_token(
    code: str,
    code_verifier: str,
    state: str,
    device_id: str
) -> Tuple[Optional[str], Optional[int]]:
    """Получает access token с помощью authorization code.

    Args:
        code (str): Код авторизации
        code_verifier (str): code_verifier для PKCE
        state (str): Параметр state
        device_id (str): Идентификатор устройства

    Returns:
        Tuple[Optional[str], Optional[int]]: (access_token, user_id) или (None, None) при ошибке
    """
    try:
        data = {
            "grant_type": "authorization_code",
            "client_id": Config.VK_APP_ID,
            "client_secret": Config.VK_APP_SECRET,
            "redirect_uri": Config.VK_REDIRECT_URI,
            "code": code,
            "code_verifier": code_verifier,
            "v": Config.VK_API_VERSION,
            "device_id": device_id,
            "state": state
        }

        response = requests.post(
            "https://id.vk.com/oauth2/auth",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        ).json()

        if "error" in response:
            logger.error(f"Ошибка VK API: {response['error_description']}")
            return None, None

        return response.get("access_token"), response.get("user_id")
    except Exception as e:
        logger.error(f"Ошибка получения токена: {e}")
        return None, None


def extract_auth_params(redirect_url: str) -> Dict[str, str]:
    """Извлекает параметры аутентификации из URL перенаправления.

    Args:
        redirect_url (str): URL перенаправления после аутентификации

    Returns:
        Dict[str, str]: Словарь с параметрами:
            - code: Код авторизации
            - state: Параметр state
            - device_id: Идентификатор устройства

    Raises:
        ValueError: Если отсутствуют обязательные параметры
    """
    try:
        parsed = urlparse(redirect_url)
        query = parse_qs(parsed.query)
        params = {
            "code": query.get("code", [None])[0],
            "state": query.get("state", [None])[0],
            "device_id": query.get("device_id", [None])[0]
        }
        
        if not params["code"] or not params["state"]:
            raise ValueError("Отсутствуют обязательные параметры: code или state")
            
        return params
    except Exception as e:
        logger.error(f"Ошибка парсинга URL: {str(e)}")
        return {}


def validate_token(token: str) -> bool:
    """Проверяет валидность access token.

    Args:
        token (str): Access token для проверки

    Returns:
        bool: True если токен валиден, иначе False
    """
    try:
        response = requests.get(
            "https://api.vk.com/method/users.get",
            params={
                "access_token": token,
                "v": Config.VK_API_VERSION,
                "fields": "id"
            },
            timeout=5
        ).json()
        
        return "error" not in response
    except requests.RequestException as e:
        logger.error(f"Ошибка проверки токена: {str(e)}")
        return False


# Инициализация логгера
logger = logging.getLogger(__name__)
