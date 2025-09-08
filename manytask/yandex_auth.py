from __future__ import annotations

import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import requests
from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import session
from requests.exceptions import HTTPError

from .abstract import AuthApi, AuthenticatedUser

logger = logging.getLogger(__name__)


class YandexAuthApiException(Exception):
    """Исключение, возбуждаемое YandexAuthApi."""

    pass


@dataclass
class YandexAuthConfig:
    """Конфигурация для YandexID OAuth API."""

    client_id: str
    client_secret: str
    dry_run: bool = False


class YandexAuthApi(AuthApi):
    """Реализация API аутентификации через YandexID OAuth."""

    def __init__(self, config: YandexAuthConfig):
        """Инициализация клиента Yandex Auth API с конфигурацией.

        :param config: Экземпляр YandexAuthConfig с настройками OAuth
        """
        self.dry_run = config.dry_run
        self.client_id = config.client_id
        self.client_secret = config.client_secret

        # Yandex OAuth API endpoints
        self.user_info_url = "https://login.yandex.ru/info"
        self.token_info_url = "https://oauth.yandex.com/token"

    def _make_auth_request(self, token: str) -> requests.Response:
        """Выполнить аутентифицированный запрос к API пользователя Яндекса.

        :param token: OAuth access token
        :return: Ответ от API Яндекса
        """
        headers = {"Authorization": f"OAuth {token}"}
        params = {"format": "json"}
        return requests.get(self.user_info_url, headers=headers, params=params)

    def _refresh_token(self, oauth: OAuth, refresh_token: str) -> dict[str, Any] | None:
        """Обновить access token используя refresh token.

        :param oauth: Экземпляр OAuth
        :param refresh_token: Refresh token
        :return: Новые токены или None если не удалось
        """
        try:
            new_tokens = oauth.remote_app.fetch_access_token(
                grant_type="refresh_token",
                refresh_token=refresh_token,
            )
            return new_tokens
        except (HTTPError, OAuthError) as e:
            logger.error(f"Failed to refresh Yandex token: {e}", exc_info=True)
            return None

    def check_user_is_authenticated(
        self,
        oauth: OAuth,
        oauth_access_token: str,
        oauth_refresh_token: str,
    ) -> bool:
        """Проверить аутентификацию пользователя через валидацию access token.

        :param oauth: Экземпляр OAuth
        :param oauth_access_token: OAuth access token
        :param oauth_refresh_token: OAuth refresh token
        :return: True если пользователь аутентифицирован, иначе False
        """
        if self.dry_run:
            logger.info("Dry run режим: пропускаем проверку аутентификации")
            return True

        response = self._make_auth_request(oauth_access_token)

        try:
            response.raise_for_status()
            return True
        except HTTPError as e:
            if e.response.status_code == HTTPStatus.UNAUTHORIZED:
                # Попытка обновить токен
                try:
                    logger.info("Yandex access token истёк. Пытаемся обновить токен.")
                    new_tokens = self._refresh_token(oauth, oauth_refresh_token)
                    if not new_tokens:
                        return False

                    new_access = new_tokens.get("access_token", "")
                    new_refresh = new_tokens.get("refresh_token", oauth_refresh_token)
                    # Попытка с новым токеном
                    response = self._make_auth_request(new_access)
                    response.raise_for_status()

                    # Обновляем сессию новыми токенами
                    session["auth"].update({"access_token": new_access, "refresh_token": new_refresh})
                    logger.info("Yandex токен успешно обновлён.")
                    return True
                except (HTTPError, OAuthError) as refresh_error:
                    logger.error(f"Не удалось валидировать обновлённый Yandex токен: {refresh_error}", exc_info=True)
                    return False

            logger.info(f"Пользователь не залогинен в Яндекс: {e}", exc_info=True)
            return False

    def get_authenticated_user(self, oauth_access_token: str) -> AuthenticatedUser:
        """Получить информацию об аутентифицированном пользователе из Яндекса.

        :param oauth_access_token: OAuth access token
        :return: Экземпляр AuthenticatedUser
        :raises YandexAuthApiException: Если не удалось получить информацию о пользователе
        """
        if self.dry_run:
            logger.info("Dry run режим: возвращаем mock пользователя")
            return AuthenticatedUser(id=12345, username="mock_user", first_name="Mock", last_name="User")

        try:
            response = self._make_auth_request(oauth_access_token)
            response.raise_for_status()
            user_data = response.json()

            # Яндекс возвращает информацию о пользователе в специфическом формате
            # Справка: https://yandex.ru/dev/id/doc/ru/user-information
            user_id = int(user_data.get("id"))
            username = user_data.get("login")
            first_name = user_data.get("first_name")
            last_name = user_data.get("last_name")

            if not user_id or not username:
                raise YandexAuthApiException("Некорректные данные пользователя от Яндекса: отсутствует id или login")

            user = AuthenticatedUser(
                id=int(user_id),
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            logger.info(f"Успешно получен Yandex пользователь: {user}")

            return user

        except HTTPError as e:
            raise YandexAuthApiException(
                f"Не удалось получить информацию о пользователе Яндекс: HTTP {e.response.status_code}"
            )
        except (KeyError, ValueError, TypeError) as e:
            raise YandexAuthApiException(f"Не удалось разобрать данные пользователя Яндекс: {e}")
        except Exception as e:
            raise YandexAuthApiException(f"Неожиданная ошибка получения пользователя Яндекс: {e}")

    def get_user_profile_info(self, oauth_access_token: str) -> dict[str, Any]:
        """Получить расширенную информацию о профиле пользователя из Яндекса.

        Это вспомогательный метод, который возвращает полные данные профиля пользователя
        которые можно использовать для регистрации пользователя и обновления профиля.

        :param oauth_access_token: OAuth access token
        :return: Полные данные профиля пользователя от Яндекса
        :raises YandexAuthApiException: Если не удалось получить информацию о пользователе
        """
        if self.dry_run:
            logger.info("Dry run режим: возвращаем mock профиль")
            return {
                "id": "12345",
                "login": "mock_user",
                "display_name": "Mock User",
                "real_name": "Mock Real User",
                "first_name": "Mock",
                "last_name": "User",
                "default_email": "mock@example.com",
            }

        try:
            response = self._make_auth_request(oauth_access_token)
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            raise YandexAuthApiException(
                f"Не удалось получить информацию профиля Яндекс: HTTP {e.response.status_code}"
            )
        except Exception as e:
            raise YandexAuthApiException(f"Неожиданная ошибка получения профиля Яндекс: {e}")

    @property
    def name(self) -> str:
        return "YandexID"
