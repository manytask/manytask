from authlib.integrations.flask_client import OAuth

from .abstract import AuthApi, AuthenticatedUser

MOCK_AUTH_USER_ID = "123"
MOCK_AUTH_USER_USERNAME = "mock_user"


class MockAuthApi(AuthApi):
    def __init__(self) -> None:
        self.user: AuthenticatedUser = AuthenticatedUser(id=MOCK_AUTH_USER_ID, username=MOCK_AUTH_USER_USERNAME)

    def check_user_is_authenticated(self, oauth: OAuth, oauth_access_token: str, oauth_refresh_token: str) -> bool:
        return True

    def get_authenticated_user(self, oauth_access_token: str) -> AuthenticatedUser:
        return self.user
