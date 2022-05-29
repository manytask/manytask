from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
import re
import datetime
from itertools import islice
from typing import Callable

import gspread
from authlib.integrations.requests_client import AssertionSession
from cachelib import BaseCache
from gspread import Cell as GCell
from gspread.utils import ValueInputOption, ValueRenderOption, a1_to_rowcol, rowcol_to_a1

from .deadlines import Deadlines
from .glab import Student
from .course import get_current_time


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
        'bold': True,
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
        'bold': True,
    }
}


# NB: numeration start with 1
@dataclass
class PublicAccountsSheetOptions:
    GROUPS_ROW: int = 1
    HEADER_ROW: int = 3
    MAX_SCORES_ROW: int = 2

    GITLAB_COLUMN: int = 1
    LOGIN_COLUMN: int = 2
    NAME_COLUMN: int = 3
    FLAGS_COLUMN: int = 4
    BONUS_COLUMN: int = 5
    TOTAL_COLUMN: int = 6
    PERCENTAGE_COLUMN: int = 7
    TASK_SCORES_START_COLUMN: int = 14


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
            cache: BaseCache,
    ):
        self._url = base_url
        self._gdoc_credentials = gdoc_credentials
        self._public_worksheet_id = public_worksheet_id
        self._public_scoreboard_sheet = public_scoreboard_sheet

        self._assertion_session = self._create_assertion_session()

        self._public_scores_sheet = self._get_sheet(public_worksheet_id, public_scoreboard_sheet)
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
        return RatingTable(self._public_scores_sheet, self._cache)

    def get_spreadsheet_url(self) -> str:
        return f'{self._url}/spreadsheets/d/{self._public_worksheet_id}#gid={self._public_scoreboard_sheet}'


class RatingTable:
    def __init__(self, worksheet: gspread.Worksheet, cache: BaseCache):
        self._cache = cache
        self.ws = worksheet

    def get_scores(self, username: str) -> dict[str, int]:
        scores = self._cache.get(f'{self.ws.id}:{username}')
        if scores is None:
            scores = {}
        return scores

    def get_all_scores(self) -> dict[str, dict[str, int]]:
        all_scores = self._cache.get(f'{self.ws.id}:scores')
        if all_scores is None:
            all_scores = {}
        return all_scores

    def get_stats(self) -> dict[str, dict[str, int]]:
        stats = self._cache.get(f'{self.ws.id}:stats')
        if stats is None:
            stats = {}
        return stats

    def get_demands(self) -> dict[str, dict[str, int]]:
        demands = self._cache.get(f'{self.ws.id}:demands')
        if demands is None:
            demands = {}
        return demands

    def get_scores_update_timestamp(self) -> str:
        timestamp = self._cache.get(f'{self.ws.id}:update-timestamp')
        if timestamp is None:
            timestamp = 'None'
        return timestamp

    def update_cached_scores(self) -> None:
        _utc_now = datetime.datetime.utcnow()

        list_of_dicts = self.ws.get_all_records(
            empty2zero=False,
            head=PublicAccountsSheetOptions.HEADER_ROW,
            default_blank='',
            expected_headers=[],
        )
        all_users_scores = {
            scores_dict["login"]: {
                k: int(v) for i, (k, v) in enumerate(scores_dict.items())
                if i >= PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN - 1 and isinstance(v, int)
            }
            for scores_dict in list_of_dicts
        }
        users_score_cache = {
            f'{self.ws.id}:{username}': scores_cache
            for username, scores_cache in all_users_scores.items()
        }
        # clear cache saving deadlines
        _deadlines = self._cache.get('__deadlines__')
        deadlines = Deadlines(_deadlines)

        _tasks_stats: defaultdict[str, int] = defaultdict(int)
        for tasks in all_users_scores.values():
            for task_name in tasks.keys():
                _tasks_stats[task_name] += 1
        tasks_stats: dict[str, float] = {
            task.name: _tasks_stats[task.name] / len(all_users_scores)
            for task in deadlines.tasks
        }
        demand_multipliers: dict[str, float] = {
            task_name: deadlines.get_low_demand_multiplier(task_stat)
            for task_name, task_stat in tasks_stats.items()
            if deadlines.get_low_demand_multiplier(task_stat) != 1
        }

        self._cache.clear()
        self._cache.set('__deadlines__', _deadlines)
        self._cache.set(f'{self.ws.id}:scores', all_users_scores)
        self._cache.set(f'{self.ws.id}:stats', tasks_stats)
        self._cache.set(f'{self.ws.id}:demands', demand_multipliers)
        self._cache.set(f'{self.ws.id}:update-timestamp', get_current_time())
        self._cache.set_many(users_score_cache)

    def store_score(self, student: Student, task_name: str, update_fn: Callable) -> int:
        try:
            student_row = self._find_login_row(student.username)
        except LoginNotFound:
            student_row = self._add_student_row(student)

        task_column = self._find_task_column(task_name)

        flags = self.ws.cell(student_row, PublicAccountsSheetOptions.FLAGS_COLUMN).value
        score_cell = self.ws.cell(student_row, task_column)
        old_score = int(score_cell.value) if score_cell.value else 0
        new_score = update_fn(flags, old_score)
        score_cell.value = new_score
        logger.info(f'Setting score = {new_score}')

        repo_link_cell = GCell(
            student_row, PublicAccountsSheetOptions.GITLAB_COLUMN, self.create_student_repo_link(student)
        )
        self.ws.update_cells([repo_link_cell, score_cell], value_input_option=ValueInputOption.user_entered)

        tasks = self._list_tasks(with_index=False)
        scores = self._get_row_values(
            student_row,
            start=PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN - 1, with_index=False
        )
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

        current_worksheet_size = PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN + len(existing_tasks) - 1
        required_worksheet_size = current_worksheet_size
        if tasks_to_create:
            required_worksheet_size = current_worksheet_size + len(tasks_to_create)

            self.ws.resize(cols=required_worksheet_size)

            cells_to_update = []
            current_group = None
            for col, task in enumerate(tasks_to_create, start=current_worksheet_size + 1):
                cells_to_update.append(GCell(PublicAccountsSheetOptions.HEADER_ROW, col, task.name))
                cells_to_update.append(GCell(PublicAccountsSheetOptions.MAX_SCORES_ROW, col, task.score))

                if task.group != current_group:
                    cells_to_update.append(GCell(PublicAccountsSheetOptions.GROUPS_ROW, col, task.group))
                    current_group = task.group
        else:
            cells_to_update = []

        if max_score:
            cells_to_update.append(GCell(
                PublicAccountsSheetOptions.GROUPS_ROW, PublicAccountsSheetOptions.TOTAL_COLUMN, str(max_score)
            ))

        if cells_to_update:
            self.ws.update_cells(cells_to_update, value_input_option=ValueInputOption.user_entered)

            self.ws.format(
                f'{rowcol_to_a1(PublicAccountsSheetOptions.GROUPS_ROW, PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN)}:'
                f'{rowcol_to_a1(PublicAccountsSheetOptions.GROUPS_ROW, required_worksheet_size)}',
                GROUP_ROW_FORMATTING
            )
            self.ws.format(
                f'{rowcol_to_a1(PublicAccountsSheetOptions.HEADER_ROW, PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN)}:'
                f'{rowcol_to_a1(PublicAccountsSheetOptions.HEADER_ROW, required_worksheet_size)}',
                HEADER_ROW_FORMATTING
            )
            self.ws.format(
                f'{rowcol_to_a1(PublicAccountsSheetOptions.MAX_SCORES_ROW, PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN)}:'
                f'{rowcol_to_a1(PublicAccountsSheetOptions.MAX_SCORES_ROW, required_worksheet_size)}',
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
        return self._get_row_values(
            PublicAccountsSheetOptions.HEADER_ROW,
            start=PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN - 1, with_index=with_index
        )

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
        all_logins = self.ws.col_values(
            PublicAccountsSheetOptions.LOGIN_COLUMN, value_render_option=ValueRenderOption.unformatted
        )

        for row, found_login in islice(enumerate(all_logins, start=1), PublicAccountsSheetOptions.HEADER_ROW, None):
            if found_login == login:
                return row

        raise LoginNotFound(f'Login {login} not found in spreadsheet')

    def _add_student_row(self, student: Student) -> int:
        logger.info(f'Adding student "{student.username}" with name "{student.name}"...')
        if len(student.name) == 0 or re.match(r'\W', student.name, flags=re.UNICODE):
            raise ValueError(f'Name "{student.name}" looks fishy')

        column_to_values_dict = {
            PublicAccountsSheetOptions.GITLAB_COLUMN: self.create_student_repo_link(student),
            PublicAccountsSheetOptions.LOGIN_COLUMN: student.username,
            PublicAccountsSheetOptions.NAME_COLUMN: student.name,
            PublicAccountsSheetOptions.FLAGS_COLUMN: None,
            PublicAccountsSheetOptions.BONUS_COLUMN: None,
            PublicAccountsSheetOptions.TOTAL_COLUMN:
                # total: sum(current row: from RATINGS_COLUMN to inf) + BONUS_COLUMN
                f'=SUM(INDIRECT(ADDRESS(ROW(); {PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN}) & ":" & ROW())) '
                f'+ INDIRECT(ADDRESS(ROW(); {PublicAccountsSheetOptions.BONUS_COLUMN}))',
            PublicAccountsSheetOptions.PERCENTAGE_COLUMN:
                # percentage: TOTAL_COLUMN / max_score cell (1st row of TOTAL_COLUMN)
                f'=INDIRECT(ADDRESS(ROW(); {PublicAccountsSheetOptions.TOTAL_COLUMN})) '
                f'/ INDIRECT(ADDRESS({PublicAccountsSheetOptions.HEADER_ROW - 1}; '
                f'{PublicAccountsSheetOptions.TOTAL_COLUMN}))'  # percentage
        }

        # fill empty columns with None
        row_values = [
            column_to_values_dict.get(i-1, None)
            for i in range(max(column_to_values_dict.items()))
        ]

        result = self.ws.append_row(
            values=row_values,
            value_input_option=ValueInputOption.user_entered,  # don't escape link
            # note logical table to upend to (gdoc implicit split it to logical tables)
            table_range=f'A{PublicAccountsSheetOptions.HEADER_ROW}',
        )

        updated_range = result['updates']['updatedRange']
        updated_range_upper_bound = updated_range.split(':')[1]
        row_count, _ = a1_to_rowcol(updated_range_upper_bound)
        return row_count

    @staticmethod
    def create_student_repo_link(student: Student) -> str:
        return f'=HYPERLINK("{student.repo}";"git")'
