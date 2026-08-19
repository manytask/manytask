from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape
from http import HTTPStatus
from pathlib import Path
from typing import IO, Any, Optional

import requests
import requests.adapters
import urllib3
from pydantic import AnyUrl

from checker.exceptions import PluginExecutionFailed

from .base import PluginABC, PluginOutput

HTTP_ERROR_STATUS_CODE = 400

# Error bodies can be whole HTML pages; keep the reported extract readable.
MAX_ERROR_BODY_LEN = 1000

# (connect, read) timeouts, so a hanging server cannot block CI forever.
DEFAULT_TIMEOUT = (10.0, 60.0)


class ManytaskPlugin(PluginABC):
    """Given score report it to the manytask.
    Datetime format in args should be: '%Y-%m-%dT%H:%M:%S.%f%z'"""

    DEFAULT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S%z"

    name = "report_score_manytask"

    class Args(PluginABC.Args):
        origin: Optional[str] = (
            None  # as pydantic does not support | in older python versions
        )
        patterns: list[str] = ["*"]
        username: str
        task_name: str
        score: (
            float | None
        )  # TODO: validate score is in [0, 1] (bonus score is higher than 1)
        report_url: AnyUrl
        report_token: str
        check_deadline: bool
        send_time: datetime = datetime.now().astimezone()

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        output: list[str] = []

        if not args.send_time.tzinfo:
            output.append(
                "Warning: No timezone provided for send_time, possible time miscalculations"
            )
        try:
            send_time_formatted = args.send_time.strftime(self.DEFAULT_TIME_FORMAT)
        except ValueError as e:
            raise PluginExecutionFailed(str(e))

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
            score = result["score"]
        except (json.JSONDecodeError, KeyError, TypeError):
            # A 2xx that is not the expected JSON usually means `report_url`
            # points at something that is not the Manytask report endpoint
            # (a proxy, a login page, a redirect...).
            details = self._describe_response_body(response)
            message = (
                f"Unable to decode response from '{args.report_url}' "
                f"(HTTP {response.status_code}). Expected JSON with a "
                f"'score' field, got:\n{details}\n"
                f"{self._REPORT_URL_HINT}"
            )
            raise PluginExecutionFailed(message, output=message)

        output.append(
            f"Report for task '{args.task_name}' for user '{args.username}', "
            f"requested score: {args.score}, result score: {score}"
        )
        return PluginOutput(output="\n".join(output))

    _REPORT_URL_HINT = (
        "Hint: `report_url` must be the full report endpoint, i.e. "
        "'https://<manytask-host>/api/<course_name>/report'."
    )

    @staticmethod
    def _post_with_retries(
        report_url: AnyUrl,
        data: dict[str, Any],
        files: dict[str, tuple[str, IO[bytes]]] | None,
    ) -> requests.Response:
        retry_strategy = urllib3.Retry(
            total=3, backoff_factor=1, status_forcelist=[408, 500, 502, 503, 504]
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        try:
            response = session.post(
                url=f"{report_url}",
                data=data,
                files=files,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            # Without this the plugin dies with a bare traceback that says
            # nothing about which URL failed or why.
            message = ManytaskPlugin._describe_request_exception(e, report_url)
            raise PluginExecutionFailed(message, output=message) from e

        if response.status_code >= HTTP_ERROR_STATUS_CODE:
            # Put the full explanation into `output` so the pipeline prints it
            # unconditionally (pipeline.py prints `error.output` always, but
            # `message` only in verbose mode).
            message = ManytaskPlugin._describe_http_error(response, report_url)
            raise PluginExecutionFailed(
                f"{response.status_code}: {response.text}",
                output=message,
            )

        return response

    @staticmethod
    def _describe_request_exception(
        exc: requests.exceptions.RequestException,
        report_url: AnyUrl,
    ) -> str:
        """Turn a transport-level failure into an actionable message."""
        if isinstance(exc, requests.exceptions.RetryError):
            reason = (
                "Manytask kept returning a retryable error (408/5xx) after "
                "3 retries. The server is likely down or overloaded."
            )
        elif isinstance(exc, requests.exceptions.ConnectTimeout):
            reason = "Timed out while connecting. The host may be firewalled or down."
        elif isinstance(exc, requests.exceptions.ReadTimeout):
            reason = "Manytask accepted the connection but did not answer in time."
        elif isinstance(exc, requests.exceptions.SSLError):
            reason = "TLS handshake failed. Check the certificate and the scheme (http vs https)."
        elif isinstance(
            exc, requests.exceptions.MissingSchema | requests.exceptions.InvalidURL
        ):
            reason = "The URL is malformed."
        elif isinstance(exc, requests.exceptions.ConnectionError):
            reason = "Could not connect. Check the host name, the port and the network."
        else:
            reason = "The request could not be completed."

        return (
            f"Failed to report the score to '{report_url}'.\n"
            f"{reason}\n"
            f"Underlying error: {type(exc).__name__}: {exc}\n"
            f"{ManytaskPlugin._REPORT_URL_HINT}"
        )

    @staticmethod
    def _describe_http_error(response: requests.Response, report_url: AnyUrl) -> str:
        """Build a readable report from a Manytask error response."""
        status = response.status_code
        try:
            reason = HTTPStatus(status).phrase
        except ValueError:
            reason = response.reason or "Unknown"

        return (
            f"Manytask rejected the report: HTTP {status} {reason} (from '{report_url}').\n"
            f"Server said: {ManytaskPlugin._describe_response_body(response)}"
        )

    @staticmethod
    def _describe_response_body(response: requests.Response) -> str:
        """Clean up an error body for display.

        Manytask answers API errors with plain text (the message, plus a 'Hint:'
        line), so it is shown as-is. Only a genuine HTML document - a proxy or
        gateway page - gets its markup stripped.

        The HTML check is deliberately narrow: Manytask quotes offending values
        in angle brackets ("Cannot parse `score` <abc>"), and a looser test would
        strip those as if they were tags, deleting the very detail being reported.
        """
        text = response.text or ""

        content_type = response.headers.get("Content-Type", "").lower()
        looks_like_html = "html" in content_type or re.match(
            r"\s*(<!doctype\s+html|<html\b)", text, re.IGNORECASE
        )

        if looks_like_html:
            text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
            text = re.sub(r"(?s)<[^>]+>", " ", text)
            text = unescape(text)
            text = " ".join(text.split())

        text = text.strip()
        if len(text) > MAX_ERROR_BODY_LEN:
            text = f"{text[:MAX_ERROR_BODY_LEN]}... (truncated)"
        return text or "<empty response body>"

    @staticmethod
    def _collect_files_to_send(
        origin: str, patterns: list[str]
    ) -> dict[str, tuple[str, IO[bytes]]]:
        source_dir = Path(origin)
        return {
            path.name: (str(path.relative_to(source_dir)), open(path, "rb"))
            for pattern in patterns
            for path in source_dir.glob(pattern)
            if path.is_file()
        }
