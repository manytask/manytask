from __future__ import annotations

import logging
import re
from itertools import islice
from typing import Callable

import gspread
from authlib.integrations.requests_client import AssertionSession
from cachelib import BaseCache
from gspread import Cell as GCell
from gspread.utils import ValueInputOption, ValueRenderOption, a1_to_rowcol, rowcol_to_a1

from .deadlines import Deadlines
from .glab import Student, User


logger = logging.getLogger(__name__)


GROUP_ROW_FORMATTING = {
    'backgroundColor': {
        'red': 182./255.,
        'green': 215./255.,
        'blue': 168./255.,
    },
    'borders': {
        'bottom': {
            'style': 'SOLID',
        },
    },
    'textFormat': {
        'fontFamily': 'Amatic SC',
        'fontSize': 24,
    }
}

HEADER_ROW_FORMATTING = {
    'backgroundColor': {
        'red': 217./255.,
        'green': 234./255.,
        'blue': 211./255.,
    },
    'borders': {
        'bottom': {
            'style': 'SOLID',
        },
    },
    'textFormat': {
        'fontFamily': 'Comfortaa',
        'fontSize': 10,
    }
}


# all start with 1
HEADER_ROW = 2
GITLAB_COLUMN = 1
LOGIN_COLUMN = 2
NAME_COLUMN = 3
FLAGS_COLUMN = 4
BONUS_COLUMN = 5
TOTAL_COLUMN = 6
PERCENTAGE_COLUMN = 7
TASK_SCORES_START_COLUMN = 14


class LoginNotFound(KeyError):
    pass


class TaskNotFound(KeyError):
    pass


class GoogleDocAPI:
    def __init__(
            self,
            base_url: str,
            gdoc_credentials: dict | None,
            public_worksheet_id: str,
            public_scoreboard_sheet: int,
            private_worksheet_id: str,
            private_accounts_sheet: int,
            private_review_sheet: int,
            cache: BaseCache,
    ):
        self._url = base_url
        self._gdoc_credentials = gdoc_credentials
        self._public_worksheet_id = public_worksheet_id
        self._public_scoreboard_sheet = public_scoreboard_sheet
        self._private_worksheet_id = private_worksheet_id
        self._private_accounts_sheet = private_accounts_sheet
        self._private_review_sheet = private_review_sheet

        self._assertion_session = self._create_assertion_session()

        self._public_sheet = self._get_sheet(public_worksheet_id, public_scoreboard_sheet)
        self._private_sheet = self._get_sheet(private_worksheet_id, private_accounts_sheet)
        self._cache = cache

    def _create_assertion_session(self) -> AssertionSession:
        """Create AssertionSession to auto refresh access to google api"""
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = self._gdoc_credentials

        header = {'alg': 'RS256'}
        if key_id := credentials.get('private_key_id', None):
            header['kid'] = key_id

        # Google puts scope in payload
        claims = {'scope': ' '.join(scopes)}
        return AssertionSession(
            token_endpoint=credentials['token_uri'],
            issuer=credentials['client_email'],
            subject=None,
            audience=credentials['token_uri'],
            grant_type=AssertionSession.JWT_BEARER_GRANT_TYPE,
            scope=' '.join(scopes),
            claims=claims,
            key=credentials['private_key'],
            header=header,
        )

    def _get_sheet(self, worksheet_id: str, sheet_id: int) -> gspread.Worksheet:
        gs: gspread.Client = gspread.Client(None, session=self._assertion_session)
        worksheet: gspread.Spreadsheet = gs.open_by_key(worksheet_id)
        return worksheet.get_worksheet(sheet_id)

    def fetch_rating_table(self) -> 'RatingTable':
        return RatingTable(self._public_sheet, self._cache)

    def fetch_private_data_table(self) -> 'PrivateDataTable':
        return PrivateDataTable(self._private_sheet)

    def get_spreadsheet_url(self) -> str:
        return f'{self._url}/spreadsheets/d/{self._public_worksheet_id}#gid={self._public_scoreboard_sheet}'


class RatingTable:
    def __init__(self, worksheet: gspread.Worksheet, cache: BaseCache):
        self._cache = cache
        self.ws = worksheet

    def get_scores(self, username: int) -> dict[str, int]:
        scores = self._cache.get(f'{self.ws.id}:{username}')
        if scores is None:
            scores = {}
        return scores

    def update_cached_scores(self) -> None:
        list_of_dicts = self.ws.get_all_records(head=HEADER_ROW, default_blank='')
        cache = {
            f'{self.ws.id}:{scores_dict["login"]}': {
                k: int(v) for i, (k, v) in enumerate(scores_dict.items())
                if i >= TASK_SCORES_START_COLUMN - 1 and isinstance(v, int)
            }
            for scores_dict in list_of_dicts
        }
        self._cache.clear()
        self._cache.set_many(cache)

    def store_score(self, student: Student, task_name: str, update_fn: Callable) -> int:
        try:
            student_row = self._find_login_row(student.username)
        except LoginNotFound:
            student_row = self._add_student_row(student)

        task_column = self._find_task_column(task_name)

        flags = self.ws.cell(student_row, FLAGS_COLUMN).value
        score_cell = self.ws.cell(student_row, task_column)
        old_score = int(score_cell.value) if score_cell.value else 0
        new_score = update_fn(flags, old_score)
        score_cell.value = new_score
        logger.info(f'Setting score = {new_score}')

        repo_link_cell = GCell(
            student_row, GITLAB_COLUMN, self.create_student_repo_link(student)
        )
        self.ws.update_cells([repo_link_cell, score_cell], value_input_option=ValueInputOption.user_entered)

        tasks = self._list_tasks(with_index=False)
        scores = self._get_row_values(student_row, start=TASK_SCORES_START_COLUMN - 1, with_index=False)
        student_scores = {
            task: score for task, score in zip(tasks, scores) if score or str(score) == '0'
        }
        logger.info(f'Actual scores: {student_scores}')

        self._cache.set(f'{self.ws.id}:{student.username}', student_scores)
        return new_score

    def sync_columns(self, tasks: list[Deadlines.Task], max_score: int | None = None) -> None:
        # TODO: maintain group orger when adding new task in added group
        logger.info(f'Syncing rating columns...')
        existing_tasks = list(self._list_tasks(with_index=False))
        existing_task_names = set(task for task in existing_tasks if task)
        tasks_to_create = [task for task in tasks if task.name not in existing_task_names]

        current_worksheet_size = TASK_SCORES_START_COLUMN + len(existing_tasks) - 1
        required_worksheet_size = current_worksheet_size
        if tasks_to_create:
            required_worksheet_size = current_worksheet_size + len(tasks_to_create)

            self.ws.resize(cols=required_worksheet_size)

            cells_to_update = []
            current_group = None
            for col, task in enumerate(tasks_to_create, start=current_worksheet_size + 1):
                cells_to_update.append(GCell(HEADER_ROW, col, task.name))

                if task.group != current_group:
                    cells_to_update.append(GCell(HEADER_ROW-1, col, task.group))
                    current_group = task.group
        else:
            cells_to_update = []

        if max_score:
            cells_to_update.append(GCell(HEADER_ROW - 1, TOTAL_COLUMN, str(max_score)))

        if cells_to_update:
            self.ws.update_cells(cells_to_update, value_input_option=ValueInputOption.user_entered)

            self.ws.format(
                f'{rowcol_to_a1(HEADER_ROW-1, TASK_SCORES_START_COLUMN)}:'
                f'{rowcol_to_a1(HEADER_ROW-1, required_worksheet_size)}',
                GROUP_ROW_FORMATTING
            )
            self.ws.format(
                f'{rowcol_to_a1(HEADER_ROW, TASK_SCORES_START_COLUMN)}:'
                f'{rowcol_to_a1(HEADER_ROW, required_worksheet_size)}',
                HEADER_ROW_FORMATTING
            )

    def _get_row_values(self, row, start=None, with_index: bool = False):
        values = self.ws.row_values(row, value_render_option=ValueRenderOption.unformatted)
        if with_index:
            values = enumerate(values, start=1)
        if start:
            values = islice(values, start, None)
        return values

    def _list_tasks(self, with_index: bool = False):
        return self._get_row_values(HEADER_ROW, start=TASK_SCORES_START_COLUMN - 1, with_index=with_index)

    def _find_task_column(self, task: str) -> int:
        logger.info(f'Looking for task "{task}"...')
        logger.info(list(self._list_tasks()))
        logger.info(str(task))
        for col, found_task in self._list_tasks(with_index=True):
            if task == found_task:
                return col
        raise TaskNotFound(f'Task "{task}" not found in spreadsheet')

    def _find_login_row(self, login: str) -> int:
        logger.info(f'Looking for student "{login}"...')
        all_logins = self.ws.col_values(LOGIN_COLUMN, value_render_option=ValueRenderOption.unformatted)

        for row, found_login in islice(enumerate(all_logins, start=1), HEADER_ROW, None):
            if found_login == login:
                return row

        raise LoginNotFound(f'Login {login} not found in spreadsheet')

    def _add_student_row(self, student: Student) -> int:
        logger.info(f'Adding student "{student.username}" with name "{student.name}"...')
        if len(student.name) == 0 or re.match(r'\W', student.name, flags=re.UNICODE):
            raise ValueError(f'Name "{student.name}" looks fishy')

        result = self.ws.append_row(
            values=[
                self.create_student_repo_link(student),
                student.username,
                student.name,
                None,  # flags
                None,  # bonus
                # total: sum(current row: from RATINGS_COLUMN to inf) + BONUS_COLUMN
                f'=SUM(INDIRECT(ADDRESS(ROW(); {TASK_SCORES_START_COLUMN}) & ":" & ROW())) '
                f'+ INDIRECT(ADDRESS(ROW(); {BONUS_COLUMN}))',
                # percentage: TOTAL_COLUMN / max_score cell (1st row of TOTAL_COLUMN)
                f'=INDIRECT(ADDRESS(ROW(); {TOTAL_COLUMN})) '
                f'/ INDIRECT(ADDRESS({HEADER_ROW - 1}; {TOTAL_COLUMN}))'  # percentage
            ],
            value_input_option=ValueInputOption.user_entered,  # don't escape link
            # note logical table to upend to (gdoc implicit split it to logical tables)
            table_range=rowcol_to_a1(HEADER_ROW, GITLAB_COLUMN),
        )

        updated_range = result['updates']['updatedRange']
        updated_range_upper_bound = updated_range.split(':')[1]
        row_count, _ = a1_to_rowcol(updated_range_upper_bound)
        return row_count

    @staticmethod
    def create_student_repo_link(student: Student) -> str:
        return f'=HYPERLINK("{student.repo}";"git")'


class PrivateDataTable:
    def __init__(self, worksheet: gspread.Worksheet):
        self.ws = worksheet

    def add_user_row(self, user: User, student: Student) -> None:
        logger.info(f'Adding user "{user.username}" into private gdoc...')
        if user.telegram:
            telegram_link = f'=HYPERLINK("https://telegram.me/{user.telegram}";"{user.telegram}")'
        else:
            telegram_link = None
        if user.lms_id:
            lms_link = f'=HYPERLINK("https://lk.yandexdataschool.ru/users/{user.lms_id}/";"{user.lms_id}")'
        else:
            lms_link = None
        _ = self.ws.append_row(
            values=[
                RatingTable.create_student_repo_link(student),
                student.name,
                student.username,
                telegram_link,
                lms_link,
            ],
            value_input_option=ValueInputOption.user_entered  # don't escape link
        )
