"""Guard the boundary between disposable lifecycle tests and development."""

from pathlib import Path
from unittest.mock import Mock, call

import pytest
import requests
from e2e import run
from e2e.test_lifecycle import Lifecycle


@pytest.mark.parametrize("container_output", ["running-container\n", "stopped-container\n"])
def test_e2e_refuses_existing_containers_before_any_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, container_output: str
) -> None:
    monkeypatch.setattr(run.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path))
    execute = Mock(return_value=container_output)
    monkeypatch.setattr(run, "command", execute)
    stack = run.Stack("unix:///dedicated-test.sock")

    with pytest.raises(RuntimeError, match="already has containers"):
        stack.prepare()

    execute.assert_called_once_with(["docker", "--host", "unix:///dedicated-test.sock", "ps", "-aq"])
    assert not stack.network_created
    assert not stack.compose_created


def test_e2e_stack_has_no_development_ports_paths_or_fixed_resource_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path))
    stack = run.Stack("unix:///dedicated-test.sock")
    stack.gitlab_ip = "172.28.10.254"
    stack.gitlab_url = "http://172.28.10.254:8929"
    stack.registry = "172.28.10.254:5050"

    config = stack.configuration()
    for service in config["services"].values():
        assert "ports" not in service
        assert "container_name" not in service
        for env_file in service.get("env_file", []):
            assert Path(env_file).parent == tmp_path
        for volume in service.get("volumes", []):
            source = volume.split(":")[0]
            assert ".env" not in source
            assert "manytask-dev" not in source
    assert all("name" not in volume for volume in config["volumes"].values())
    assert config["networks"]["default"]["name"].startswith(stack.project)
    assert "--env-file" in stack.compose
    assert str(tmp_path / "empty.env") in stack.compose


def test_e2e_still_tears_down_and_erases_credentials_if_log_collection_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path))
    stack = run.Stack("unix:///dedicated-test.sock")
    stack.compose_created = True
    stack.network_created = True
    for name in ["app.env", "compose.yml", "runner-token", "askpass.sh"]:
        (tmp_path / name).write_text("generated test credential")
    execute = Mock(side_effect=[RuntimeError("log collection unavailable"), "", "", ""])
    monkeypatch.setattr(run, "command", execute)

    with pytest.raises(RuntimeError, match="cleanup was incomplete"):
        stack.cleanup()

    calls = [call.args[0] for call in execute.call_args_list]
    assert stack.compose + ["down", "--volumes", "--remove-orphans", "--timeout", "30"] in calls
    assert stack.docker + ["network", "rm", stack.network] in calls
    assert not any((tmp_path / name).exists() for name in ["app.env", "compose.yml", "runner-token", "askpass.sh"])


def test_e2e_follows_gitlab_html_oauth_redirect() -> None:
    lifecycle = Lifecycle.__new__(Lifecycle)
    lifecycle.app = "http://manytask:5050"
    response = requests.Response()
    response.url = "http://gitlab:8929/oauth/authorize"
    callback = "http://manytask:5050/login_finish?code=test-code&state=test-state"
    response._content = f'<html>Redirecting <a href="{callback}">Click here</a></html>'.encode()
    session = Mock(spec=requests.Session)

    result = lifecycle.finish_oauth(session, response)

    session.get.assert_called_once_with(callback, timeout=60)
    assert result == session.get.return_value


def test_e2e_oauth_failure_diagnostic_redacts_query_credentials() -> None:
    lifecycle = Lifecycle.__new__(Lifecycle)
    lifecycle.app = "http://manytask:5050"
    lifecycle.redactions = []
    response = requests.Response()
    response.url = "http://gitlab:8929/oauth/authorize"
    response._content = b"Unexpected response: http://other-service/callback?code=private-code"

    with pytest.raises(AssertionError) as error:
        lifecycle.finish_oauth(Mock(spec=requests.Session), response)

    assert "private-code" not in str(error.value)
    assert "query-redacted" in str(error.value)


def test_e2e_cancels_only_active_setup_pipelines_in_its_project() -> None:
    lifecycle = Lifecycle.__new__(Lifecycle)
    lifecycle.evidence = {}
    lifecycle.gl = Mock(
        side_effect=[
            [
                {"id": 10, "status": "running"},
                {"id": 11, "status": "pending"},
                {"id": 12, "status": "success"},
                {"id": 13, "status": "skipped"},
            ],
            {},
        ]
    )

    lifecycle.cancel_setup_pipelines(project=2, expected=10)

    assert lifecycle.gl.call_args_list == [
        call("GET", "projects/2/pipelines", params={"per_page": 100}),
        call("POST", "projects/2/pipelines/11/cancel"),
    ]
    assert lifecycle.evidence["setup_pipelines_canceled"] == [11]
