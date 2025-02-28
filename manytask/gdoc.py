from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from itertools import islice
from typing import Any, Callable, Iterable

import gspread
from authlib.integrations.requests_client import AssertionSession
from cachelib import BaseCache
from google.auth.credentials import AnonymousCredentials
from gspread import Cell as GCell
from gspread.utils import ValueInputOption, ValueRenderOption, a1_to_rowcol

from .abstract import StorageApi, StoredUser, ViewerApi
from .config import ManytaskDeadlinesConfig, ManytaskGroupConfig, ManytaskTaskConfig
from .glab import Student

logger = logging.getLogger(__name__)


GROUP_ROW_FORMATTING = {
    "backgroundColor": {
        "red": 182.0 / 255.0,
        "green": 215.0 / 255.0,
        "blue": 168.0 / 255.0,
    },
    "borders": {
        "bottom": {
            "style": "SOLID",
        },
    },
    "textFormat": {
        "fontFamily": "Amatic SC",
        "fontSize": 24,
        "bold": True,
    },
}

HEADER_ROW_FORMATTING = {
    "backgroundColor": {
        "red": 217.0 / 255.0,
        "green": 234.0 / 255.0,
        "blue": 211.0 / 255.0,
    },
    "borders": {
        "bottom": {
            "style": "SOLID",
        },
    },
    "textFormat": {
        "fontFamily": "Comfortaa",
        "fontSize": 10,
        "bold": True,
    },
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


@dataclass
class GDocConfig:
    """Configuration for Google Docs API connection and spreadsheet settings."""

    base_url: str
    gdoc_credentials: dict[str, Any]
    public_worksheet_id: str
    public_scoreboard_sheet: int
    cache: BaseCache
    testing: bool = False


class GoogleDocApi(ViewerApi, StorageApi):
    def __init__(
        self,
        config: GDocConfig,
    ):
        """Initialize Google Docs client with configuration.

        :param config: GDocConfig instance containing all necessary settings
        """
        self.base_url = config.base_url
        self.gdoc_credentials = config.gdoc_credentials
        self.public_worksheet_id = config.public_worksheet_id
        self.public_scoreboard_sheet = config.public_scoreboard_sheet
        self.cache = config.cache
        self.testing = config.testing

        if self.testing:
            return  # TODO: cover all methods

        self._assertion_session = self._create_assertion_session()

        self._public_scores_sheet = self._get_sheet(self.public_worksheet_id, self.public_scoreboard_sheet)

        self.ws = self.get_scores_sheet()

    def _create_assertion_session(self) -> AssertionSession:
        """Create AssertionSession to auto refresh access to google api"""
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = self.gdoc_credentials

        header = {"alg": "RS256"}
        if key_id := credentials.get("private_key_id", None):
            header["kid"] = key_id

        # Google puts scope in payload
        claims = {"scope": " ".join(scopes)}
        return AssertionSession(
            token_endpoint=credentials["token_uri"],
            issuer=credentials["client_email"],
            subject=None,
            audience=credentials["token_uri"],
            grant_type=AssertionSession.JWT_BEARER_GRANT_TYPE,
            scope=" ".join(scopes),
            claims=claims,
            key=credentials["private_key"],
            header=header,
        )

    def _get_sheet(
        self,
        worksheet_id: str,
        sheet_id: int,
    ) -> gspread.Worksheet:
        gs: gspread.Client = gspread.Client(AnonymousCredentials(), session=self._assertion_session)
        worksheet: gspread.Spreadsheet = gs.open_by_key(worksheet_id)
        return worksheet.get_worksheet(sheet_id)

    def get_scores_sheet(self) -> gspread.Worksheet:
        return self._public_scores_sheet

    def get_scoreboard_url(self) -> str:
        return f"{self.base_url}/spreadsheets/d/{self.public_worksheet_id}#gid={self.public_scoreboard_sheet}"

    def get_scores(
        self,
        username: str,
    ) -> dict[str, int]:
        scores = self.cache.get(f"{self.ws.id}:{username}")
        if scores is None:
            scores = {}
        return scores

    def get_bonus_score(
        self,
        username: str,
    ) -> int:
        bonus_scores = self.cache.get(f"{self.ws.id}:bonus")
        if bonus_scores is None:
            return 0
        return bonus_scores.get(username, 0)

    def get_stored_user(
        self,
        student: Student,
    ) -> StoredUser:
        return StoredUser(username=student.username, course_admin=False)

    def sync_stored_user(
        self,
        student: Student,
    ) -> StoredUser:
        return self.get_stored_user(student)

    def get_all_scores(self) -> dict[str, dict[str, int]]:
        all_scores = self.cache.get(f"{self.ws.id}:scores")
        if all_scores is None:
            all_scores = {}
        return all_scores

    def get_stats(self) -> dict[str, float]:
        stats = self.cache.get(f"{self.ws.id}:stats")
        if stats is None:
            stats = {}
        return stats

    def get_scores_update_timestamp(self) -> str:
        timestamp = self.cache.get(f"{self.ws.id}:update-timestamp")
        if timestamp is None:
            timestamp = "None"
        return timestamp

    def update_cached_scores(self) -> None:
        raise NotImplementedError("Deprecated api class")

    def store_score(
        self,
        student: Student,
        task_name: str,
        update_fn: Callable[..., Any],
    ) -> int:
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
        logger.info(f"Setting score = {new_score}")

        repo_link_cell = GCell(
            student_row,
            PublicAccountsSheetOptions.GITLAB_COLUMN,
            self.create_student_repo_link(student),
        )
        self.ws.update_cells(
            [repo_link_cell, score_cell],
            value_input_option=ValueInputOption.user_entered,
        )

        tasks = self._list_tasks(with_index=False)
        scores = self._get_row_values(
            student_row,
            start=PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN - 1,
            with_index=False,
        )
        student_scores = {task: score for task, score in zip(tasks, scores) if score or str(score) == "0"}
        logger.info(f"Actual scores: {student_scores}")

        self.cache.set(f"{self.ws.id}:{student.username}", student_scores)
        return new_score

    def sync_columns(
        self,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None:
        raise NotImplementedError("Deprecated api class")

    def _get_row_values(
        self,
        row: int,
        start: int | None = None,
        with_index: bool = False,
    ) -> Iterable[Any]:
        values: Iterable[Any] = self.ws.row_values(row, value_render_option=ValueRenderOption.unformatted)
        if with_index:
            values = enumerate(values, start=1)
        if start:
            values = islice(values, start, None)
        return values

    def _list_tasks(
        self,
        with_index: bool = False,
    ) -> Iterable[Any]:
        return self._get_row_values(
            PublicAccountsSheetOptions.HEADER_ROW,
            start=PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN - 1,
            with_index=with_index,
        )

    def _find_task_column(
        self,
        task: str,
    ) -> int:
        logger.info(f'Looking for task "{task}"...')
        logger.info(list(self._list_tasks()))
        logger.info(str(task))
        for col, found_task in self._list_tasks(with_index=True):
            if task == found_task:
                return col
        raise TaskNotFound(f'Task "{task}" not found in spreadsheet')

    def _find_login_row(
        self,
        login: str,
    ) -> int:
        logger.info(f'Looking for student "{login}"...')
        all_logins = self.ws.col_values(
            PublicAccountsSheetOptions.LOGIN_COLUMN,
            value_render_option=ValueRenderOption.unformatted,
        )

        for row, found_login in islice(enumerate(all_logins, start=1), PublicAccountsSheetOptions.HEADER_ROW, None):
            if str(found_login) == login:
                return row

        raise LoginNotFound(f"Login {login} not found in spreadsheet")

    def _add_student_row(
        self,
        student: Student,
    ) -> int:
        logger.info(f'Adding student "{student.username}" with name "{student.name}"...')
        if len(student.name) == 0 or re.match(r"\W", student.name, flags=re.UNICODE):
            raise ValueError(f'Name "{student.name}" looks fishy')

        column_to_values_dict = {
            PublicAccountsSheetOptions.GITLAB_COLUMN: self.create_student_repo_link(student),
            PublicAccountsSheetOptions.LOGIN_COLUMN: student.username,
            PublicAccountsSheetOptions.NAME_COLUMN: student.name,
            PublicAccountsSheetOptions.FLAGS_COLUMN: "",
            PublicAccountsSheetOptions.BONUS_COLUMN: "",
            PublicAccountsSheetOptions.TOTAL_COLUMN:
            # total: sum(current row: from RATINGS_COLUMN to inf) + BONUS_COLUMN
            f'=SUM(INDIRECT(ADDRESS(ROW(); {PublicAccountsSheetOptions.TASK_SCORES_START_COLUMN}) & ":" & ROW())) '
            f"+ INDIRECT(ADDRESS(ROW(); {PublicAccountsSheetOptions.BONUS_COLUMN}))",
            PublicAccountsSheetOptions.PERCENTAGE_COLUMN:
            # percentage: TOTAL_COLUMN / max_score cell (1st row of TOTAL_COLUMN)
            f"=IFERROR(INDIRECT(ADDRESS(ROW(); {PublicAccountsSheetOptions.TOTAL_COLUMN})) "
            f"/ INDIRECT(ADDRESS({PublicAccountsSheetOptions.HEADER_ROW - 1}; "
            f"{PublicAccountsSheetOptions.TOTAL_COLUMN})); 0)",  # percentage
        }

        # fill empty columns with empty string
        row_values = [column_to_values_dict.get(i + 1, "") for i in range(max(column_to_values_dict.keys()))]

        result = self.ws.append_row(
            values=row_values,
            value_input_option=ValueInputOption.user_entered,  # don't escape link
            # note logical table to upend to (gdoc implicit split it to logical tables)
            table_range=f"A{PublicAccountsSheetOptions.HEADER_ROW}",
        )

        updated_range = result["updates"]["updatedRange"]
        updated_range_upper_bound = updated_range.split(":")[1]
        row_count, _ = a1_to_rowcol(updated_range_upper_bound)
        return row_count

    @staticmethod
    def create_student_repo_link(
        student: Student,
    ) -> str:
        return f'=HYPERLINK("{student.repo}";"git")'

    def find_task(self, task_name: str) -> tuple[ManytaskGroupConfig, ManytaskTaskConfig]:
        raise NotImplementedError("Deprecated api class")

    def get_groups(
        self,
        enabled: bool | None = None,
        started: bool | None = None,
        now: datetime | None = None,
    ) -> list[ManytaskGroupConfig]:
        raise NotImplementedError("Deprecated api class")

    def get_now_with_timezone(self) -> datetime:
        raise NotImplementedError("Deprecated api class")

    def update_task_groups_from_config(
        self,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None:
        """Empty implementation for GoogleDocApi as it doesn't need task group management.
        Task groups are managed directly in the spreadsheet during sync_columns.

        :param config_data: Raw config data from yaml
        """
        pass

    def sync_and_get_admin_status(self, course_name: str, student: Student) -> bool:
        return False

    def check_user_on_course(self, course_name: str, student: Student) -> bool:
        return False
