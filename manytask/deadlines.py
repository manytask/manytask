import logging
from typing import List, Any
from collections import namedtuple
import random

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
        deadlines = [
            {
                'group': f'group_{i}',
                'start': '01-01-2010 00:00',
                'deadline': '01-01-2010 00:01',
                'second_deadline': '01-01-2010 00:02' if random.random() > 0.5 else '01-01-2010 00:01',
                'hw': i == 2,
                'tasks': [
                    {
                        'task': f'task_{i}_{j}',
                        'score': random.randint(1, 12) * 10,
                    }
                    for j in range(random.randint(1, 7))
                ],
            }
            for i in range(10)
        ]
        return Deadlines(reversed(deadlines))


class Deadlines:
    Task = namedtuple('Task', ('name', 'group'))

    def __init__(self, config: list[dict]):
        self.groups = self._parse_groups(config)

    @staticmethod
    def _parse_groups(config: list[dict]) -> List[course.Group]:
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
    def _parse_tasks(config: dict[str, Any]) -> List[course.Task]:
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
    def open_groups(self) -> List[course.Group]:
        return [group for group in self.groups if group.is_open]

    @property
    def tasks(self) -> List[Task]:
        return [
            self.Task(task.name, group.name) for group in reversed(self.groups)
            for task in group.tasks
        ]

    @property
    def tasks_started(self) -> List[Task]:
        return [
            self.Task(task.name, group.name) for group in reversed(self.groups)
            for task in group.tasks if task.is_started()
        ]

    @property
    def max_score(self) -> int:
        return sum(task.score for group in self.groups for task in group.tasks)

    @property
    def max_score_started(self) -> int:
        return sum(task.score for group in self.groups for task in group.tasks if task.is_started())
