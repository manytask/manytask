from authlib.integrations.flask_client import OAuth

from .abstract import AuthApi, AuthenticatedUser

# Mock users configuration
MOCK_USERS = {
    "admin": {"id": 1, "username": "admin", "password": "admin"},
    "user": {"id": 2, "username": "user", "password": "user"},
}


class MockAuthApi(AuthApi):
    def __init__(self) -> None:
        # Default to admin user for backward compatibility
        self.current_user: AuthenticatedUser = AuthenticatedUser(
            id=MOCK_USERS["admin"]["id"],
            username=MOCK_USERS["admin"]["username"]
        )

    def check_user_is_authenticated(self, oauth: OAuth, oauth_access_token: str, oauth_refresh_token: str) -> bool:
        return True

    def get_authenticated_user(self, oauth_access_token: str) -> AuthenticatedUser:
        return self.current_user
    
    def set_current_user(self, username: str) -> None:
        """Set the current authenticated user for mock authentication."""
        if username in MOCK_USERS:
            user_data = MOCK_USERS[username]
            self.current_user = AuthenticatedUser(id=user_data["id"], username=user_data["username"])
