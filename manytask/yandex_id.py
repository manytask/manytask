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


class YandexIDApiException(Exception):
    pass


@dataclass
class YandexIDConfig:
    dry_run: bool = False


class YandexIDApi(AuthApi):
    def __init__(self, config: YandexIDConfig):
        self.dry_run = config.dry_run

        # Yandex OAuth API endpoints
        self.user_info_url = "https://login.yandex.ru/info"
        self.token_info_url = "https://oauth.yandex.com/token"

    def _make_auth_request(self, token: str) -> requests.Response:
        headers = {"Authorization": f"OAuth {token}"}
        params = {"format": "json"}
        return requests.get(self.user_info_url, headers=headers, params=params)

    def _refresh_token(self, oauth: OAuth, refresh_token: str) -> dict[str, Any] | None:
        try:
            new_tokens = oauth.auth_provider.fetch_access_token(
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
        if self.dry_run:
            logger.info("Dry run mode: skipping authentication check")
            return True

        response = self._make_auth_request(oauth_access_token)

        try:
            response.raise_for_status()
            return True
        except HTTPError as e:
            if e.response.status_code == HTTPStatus.UNAUTHORIZED:
                try:
                    logger.info("YandexID access token expired. Trying to refresh token.")
                    new_tokens = self._refresh_token(oauth, oauth_refresh_token)
                    if not new_tokens:
                        return False

                    new_access = new_tokens.get("access_token", "")
                    new_refresh = new_tokens.get("refresh_token", oauth_refresh_token)
                    response = self._make_auth_request(new_access)
                    response.raise_for_status()

                    session["auth"].update({"access_token": new_access, "refresh_token": new_refresh})
                    logger.info("YandexID token refreshed successfully.")
                    return True
                except (HTTPError, OAuthError) as refresh_error:
                    logger.error(f"Failed to validate refreshed YandexID token: {refresh_error}", exc_info=True)
                    return False

            logger.info(f"User is not logged to YandexID: {e}", exc_info=True)
            return False

    def get_authenticated_user(self, oauth_access_token: str) -> AuthenticatedUser:
        if self.dry_run:
            logger.info("Dry run mode: returning mock user")
            return AuthenticatedUser(id="12345", username="mock_user")

        try:
            response = self._make_auth_request(oauth_access_token)
            response.raise_for_status()
            user_data = response.json()

            # YandexID returns user information in a specific format: https://yandex.ru/dev/id/doc/ru/user-information
            user_id = int(user_data.get("id"))
            username = user_data.get("login")

            if not user_id or not username:
                raise YandexIDApiException("Invalid user data from YandexID: id or login is missing")

            user = AuthenticatedUser(
                id=str(user_id),
                username=username,
            )
            logger.info(f"Successfully retrieved YandexID user: {user}")

            return user

        except HTTPError as e:
            raise YandexIDApiException(f"Failed to get user information from YandexID: HTTP {e.response.status_code}")
        except (KeyError, ValueError, TypeError) as e:
            raise YandexIDApiException(f"Failed to parse user data from YandexID: {e}")
        except Exception as e:
            raise YandexIDApiException(f"Unexpected error getting YandexID user: {e}")
