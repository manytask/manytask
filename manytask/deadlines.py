import logging
from collections import namedtuple
from datetime import datetime, timedelta
from typing import Any

import yaml
from cachelib import BaseCache

from . import course

logger = logging.getLogger(__name__)


class DeadlinesAPI:
    def __init__(self, cache: BaseCache):
        self._file_path = '.deadlines.yml'
        self._cache = cache

    def store(self, content: list[dict]) -> None:
        logger.info('Store deadlines...')
        Deadlines(content)  # For validation purposes
        self._cache.set('__deadlines__', content)

    def fetch(self) -> 'Deadlines':
        logger.info('Fetching deadlines...')
        deadlines = self._cache.get('__deadlines__')
        return Deadlines(deadlines)

    def fetch_debug(self) -> 'Deadlines':
        logger.info('Fetching debug deadlines...')
        total_groups = 11
        _now = datetime.now()
        deadlines = [
            {
                'group': f'group_{i}',
                'start': (_now + timedelta(days=i-10)).strftime('%d-%m-%Y 18:00'),
                'deadline': (_now + timedelta(days=i-5)).strftime('%d-%m-%Y 23:59'),
                'second_deadline': (_now + timedelta(days=i-5+(i % 2))).strftime('%d-%m-%Y 23:59'),
                'hw': i == 2,
                'tasks': [
                    {
                        'task': f'task_{i}_{j}',
                        'score': (j+1)*10,
                    }
                    for j in range(total_groups-i)
                ],
            }
            for i in range(total_groups)
        ]
        self._cache.set('__deadlines__', deadlines)
        return Deadlines(deadlines[::-1])


class Deadlines:
    Task = namedtuple('Task', ('name', 'group', 'score'))

    def __init__(self, config: list[dict]):
        self.groups = self._parse_groups(config)

    @staticmethod
    def get_low_demand_multiplier(demand: float) -> float:
        # if demand <= 0.5:
        #     demand_multiplier = 1 + 0.1 * 2 * (0.5 - demand)
        # else:
        #     demand_multiplier = 1

        if demand <= 0.25:
            demand_multiplier = 1 + 0.1 * (1 - demand)
        else:
            demand_multiplier = 1

        return min(demand_multiplier, 2)

    @staticmethod
    def _parse_groups(config: list[dict]) -> list[course.Group]:
        task_names = []
        groups = []
        if config is None:
            return []
        for group_config in config:
            if not group_config.get('enabled', True):
                continue
            group = course.Group(
                name=group_config['group'],
                start=group_config['start'],
                deadline=group_config['deadline'],
                second_deadline=group_config['second_deadline'],
                tasks=Deadlines._parse_tasks(group_config),
                hw=group_config.get('hw', False),
            )
            groups.append(group)
            task_names.extend(task.name for task in group.tasks)

        if len(task_names) != len(set(task_names)):
            raise ValueError('Duplicate task names')
        return groups

    @staticmethod
    def _parse_tasks(config: dict[str, Any]) -> list[course.Task]:
        tasks_config = config.get('tasks', [])
        return [
            course.Task(
                name=c['task'],
                score=c['score'],
                tags=c.get('tags', []),
                start=config['start'],
                deadline=config['deadline'],
                second_deadline=config['second_deadline'],
                scoring_func=c.get('scoring_func', 'max')
            ) for c in tasks_config
            if c.get('enabled', True)
        ]

    def find_task(self, name: str) -> course.Task:
        logger.info(f'Searching task "{name}"...')
        for group in self.groups:
            if not group.is_open:
                logger.info(f'Skipping closed group "{group.name}"...')
                continue
            for task in group.tasks:
                if task.name == name:
                    return task
        raise KeyError(f'Task "{name}" not found')

    @property
    def open_groups(self) -> list[course.Group]:
        return [group for group in self.groups if group.is_open]

    @property
    def tasks(self) -> list[Task]:
        return [
            self.Task(task.name, group.name, task.score) for group in reversed(self.groups)
            for task in group.tasks
        ]

    @property
    def tasks_started(self) -> list[Task]:
        return [
            self.Task(task.name, group.name, task.score) for group in reversed(self.groups)
            for task in group.tasks if task.is_started()
        ]

    @property
    def max_score(self) -> int:
        return sum(task.score for group in self.groups for task in group.tasks)

    @property
    def max_score_started(self) -> int:
        return sum(task.score for group in self.groups for task in group.tasks if task.is_started())
