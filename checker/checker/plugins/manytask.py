from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import IO, Any, Optional

import requests
import requests.adapters
import urllib3
from pydantic import AnyUrl

from checker.exceptions import PluginExecutionFailed

from .base import PluginABC, PluginOutput


class ManytaskPlugin(PluginABC):
    """Given score report it to the manytask.
    Datetime format in args should be: '%Y-%m-%dT%H:%M:%S.%f%z'"""

    DEFAULT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S%z"

    name = "report_score_manytask"

    class Args(PluginABC.Args):
        origin: Optional[str] = None  # as pydantic does not support | in older python versions
        patterns: list[str] = ["*"]
        username: str
        task_name: str
        score: float | None  # TODO: validate score is in [0, 1] (bonus score is higher than 1)
        report_url: AnyUrl
        report_token: str
        check_deadline: bool
        send_time: datetime = datetime.now().astimezone()

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        output: list[str] = []

        if not args.send_time.tzinfo:
            output.append("Warning: No timezone provided for send_time, possible time miscalculations")
        try:
            send_time_formatted = args.send_time.strftime(self.DEFAULT_TIME_FORMAT)
        except ValueError as e:
            raise PluginExecutionFailed(e)

        # Do not expose token in logs.
        data = {
            "token": args.report_token,
            "task": args.task_name,
            "username": args.username,
            "score": args.score,
            "check_deadline": args.check_deadline,
            "submit_time": send_time_formatted,
        }

        files = None
        if args.origin is not None:
            files = self._collect_files_to_send(args.origin, args.patterns)

        if verbose:
            output.append(str(files))

        response = self._post_with_retries(args.report_url, data, files)

        try:
            result = response.json()
            output.append(
                f"Report for task '{args.task_name}' for user '{args.username}', "
                f"requested score: {args.score}, result score: {result['score']}"
            )
            return PluginOutput(output="\n".join(output))
        except (json.JSONDecodeError, KeyError):
            raise PluginExecutionFailed("Unable to decode response")

    @staticmethod
    def _post_with_retries(
        report_url: AnyUrl,
        data: dict[str, Any],
        files: dict[str, tuple[str, IO[bytes]]] | None,
    ) -> requests.Response:
        retry_strategy = urllib3.Retry(total=3, backoff_factor=1, status_forcelist=[408, 500, 502, 503, 504])
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        response = session.post(url=f"{report_url}", data=data, files=files)

        if response.status_code >= 400:
            raise PluginExecutionFailed(f"{response.status_code}: {response.text}")

        return response

    @staticmethod
    def _collect_files_to_send(origin: str, patterns: list[str]) -> dict[str, tuple[str, IO[bytes]]]:
        source_dir = Path(origin)
        return {
            path.name: (str(path.relative_to(source_dir)), open(path, "rb"))
            for pattern in patterns
            for path in source_dir.glob(pattern)
            if path.is_file()
        }
