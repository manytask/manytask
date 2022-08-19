from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class CourseConfig:
    name: str

    deadlines: str
    second_deadline_max: float = 0.5
    low_demand_bonus_bound: float = 0.2
    max_low_demand_bonus: float = 1.0

    lms_url: str | None = None
    telegram_channel_invite: str | None = None
    telegram_chat_invite: str | None = None


@dataclass
class Config:
    # tokens
    registration_secret: str
    tester_token: str

    # utils
    cache_dir: str
    solutions_dir: str

    # gitlab
    gitlab_url: str
    gitlab_admin_token: str
    # gitlab course repos
    gitlab_course_private_repo: str
    gitlab_course_public_repo: str
    gitlab_course_students_group: str
    # gitlab oauth2
    gitlab_client_id: str
    gitlab_client_secret: str

    # google sheets
    gdoc_url: str
    gdoc_account_credentials_base64: str  # base64 encoded json
    # google public sheet
    gdoc_spreadsheet_id: str
    gdoc_scoreboard_sheet: int

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            # tokens
            registration_secret=os.environ['REGISTRATION_SECRET'],
            tester_token=os.environ['TESTER_TOKEN'],

            # utils
            cache_dir=os.environ['CACHE_DIR'],
            solutions_dir=os.environ['SOLUTIONS_DIR'],

            # gitlab
            gitlab_url=os.environ.get('GITLAB_URL', 'https://gitlab.manytask.org'),
            gitlab_admin_token=os.environ['GITLAB_ADMIN_TOKEN'],
            # gitlab course repos
            gitlab_course_private_repo=os.environ['GITLAB_COURSE_PUBLIC_REPO'],
            gitlab_course_public_repo=os.environ['GITLAB_COURSE_PUBLIC_REPO'],
            gitlab_course_students_group=os.environ['GITLAB_COURSE_STUDENTS_GROUP'],
            # gitlab oauth2
            gitlab_client_id=os.environ['GITLAB_CLIENT_ID'],
            gitlab_client_secret=os.environ['GITLAB_CLIENT_SECRET'],

            # google sheets (credentials base64 encoded json)
            gdoc_url=os.environ.get('GDOC_URL', 'https://docs.google.com'),
            gdoc_account_credentials_base64=os.environ['GDOC_ACCOUNT_CREDENTIALS_BASE64'],
            # google public sheet
            gdoc_spreadsheet_id=os.environ['GDOC_SPREADSHEET_ID'],
            gdoc_scoreboard_sheet=int(os.environ.get('GDOC_SCOREBOARD_SHEET', 0)),
        )


@dataclass
class DebugConfig(Config):
    # tokens
    registration_secret: str = 'registration_secret'
    tester_token: str = 'tester_token'

    # utils
    cache_dir: str = './tmp/cache'
    solutions_dir: str = './tmp/solutions'

    # gitlab
    gitlab_url: str = 'https://gitlab.manytask.org'
    gitlab_admin_token: str = ''
    # gitlab course repos
    gitlab_course_private_repo: str = ''
    gitlab_course_public_repo: str = ''
    gitlab_course_students_group: str = ''
    # gitlab oauth2
    gitlab_client_id: str = ''
    gitlab_client_secret: str = ''

    # google sheets
    gdoc_url: str = ''
    gdoc_account_credentials_base64: str = ''
    # google public sheet
    gdoc_spreadsheet_id: str = ''
    gdoc_scoreboard_sheet: int = ''

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            gdoc_url='https://docs.google.com',
            gdoc_account_credentials_base64=os.environ['GDOC_ACCOUNT_CREDENTIALS_BASE64'],
            gdoc_spreadsheet_id=os.environ.get('GDOC_SPREADSHEET_ID', '1cRah9NC5Nl7_NyzttC3Q5BtrnbdO6KyaG7gx5ZGusTM'),
            gdoc_scoreboard_sheet=int(os.environ.get('GDOC_SCOREBOARD_SHEET', 0)),
        )


@dataclass
class TestConfig(DebugConfig):
    # google sheets
    gdoc_url: str = ''
    gdoc_account_credentials_base64: str = ''
    # google public sheet
    gdoc_spreadsheet_id: str = ''
    gdoc_scoreboard_sheet: int = 0
