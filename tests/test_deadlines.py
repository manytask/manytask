import pathlib
import typing
from typing import Any

import yaml

from manytask.deadlines import Deadlines


class TestDeadlines:

    def test_bonus(self) -> None:
        path = pathlib.Path(__file__).parent / '.deadlines.test.yml'
        with open(path, 'r') as f:
            deadlines = Deadlines(yaml.load(f, Loader=yaml.SafeLoader))
        assert deadlines.max_score == 40
        assert deadlines.max_score_started == 40
        assert deadlines.find_task("task_0_0").is_bonus
        assert not deadlines.find_task("task_0_1").is_bonus
