import os
from dataclasses import dataclass


@dataclass
class Config:
    # general
    course_name: str = os.environ.get('COURSE_NAME')

    # tokens
    registration_secret: str = os.environ.get('REGISTRATION_SECRET')
    tester_token: str = os.environ.get('TESTER_TOKEN')

    # utils
    cache_dir: str = os.environ.get('CACHE_DIR')

    # info links
    lms_url: str = os.environ.get('LMS_URL', 'https://lk.yandexdataschool.ru/')
    telegram_invite_link: str = os.environ.get('TELEGRAM_INVITE_LINK', '')

    # gitlab
    gitlab_url: str = os.environ.get('GITLAB_URL', 'https://gitlab.manytask.org')
    gitlab_admin_token: str = os.environ.get('GITLAB_ADMIN_TOKEN')
    # gitlab course repos
    gitlab_course_public_repo: str = os.environ.get('GITLAB_COURSE_PUBLIC_REPO')
    gitlab_course_students_group: str = os.environ.get('GITLAB_COURSE_STUDENTS_GROUP')
    gitlab_course_admins_group: str = os.environ.get('GITLAB_COURSE_ADMINS_GROUP', None)
    # gitlab oauth2
    gitlab_client_id: str = os.environ.get('GITLAB_CLIENT_ID')
    gitlab_client_secret: str = os.environ.get('GITLAB_CLIENT_SECRET')

    # google sheets
    gdoc_url: str = os.environ.get('GDOC_URL', 'https://docs.google.com')
    gdoc_account: str = os.environ.get('GDOC_ACCOUNT')  # google docs credentials base64 encoded json
    # google public sheet
    gdoc_spreadsheet_id: str = os.environ.get('GDOC_SPREADSHEET_ID')
    gdoc_scoreboard_sheet: int = os.environ.get('GDOC_SCOREBOARD_SHEET', 0)
    # google private sheet
    gdoc_private_spreadsheet_id: str = os.environ.get('GDOC_PRIVATE_SPREADSHEET_ID')
    gdoc_private_review_sheet: int = os.environ.get('GDOC_PRIVATE_REVIEW_SHEET', 0)


class DebugConfig(Config):
    # general
    course_name: str = 'test'

    # tokens
    registration_secret: str = 'registration_secret'
    tester_token: str = 'tester_token'

    # utils
    cache_dir: str = './cache'

