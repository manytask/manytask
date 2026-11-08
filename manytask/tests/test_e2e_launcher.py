"""Regression checks for credentials crossing the isolated e2e launcher boundary."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from e2e import run


@pytest.fixture()
def stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> run.Stack:
    monkeypatch.setattr(run, "COMPONENT", tmp_path)
    result = run.Stack("unix:///test-only/docker.sock")
    result.gitlab_ip = "172.28.1.254"
    result.gitlab_url = "http://172.28.1.254:8929"
    result.registry = "172.28.1.254:5050"
    return result


def test_saved_compose_contains_references_without_credentials(stack: run.Stack) -> None:
    config = stack.configuration()
    content = yaml.safe_dump(config)

    assert stack.password not in content
    assert stack.course_token not in content
    assert config["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"] == "${E2E_STACK_PASSWORD}"
    assert config["services"]["manytask"]["environment"]["GITLAB_ADMIN_TOKEN"] == "${E2E_GITLAB_ADMIN_TOKEN:-}"
    assert "env_file" not in config["services"]["manytask"]
    assert config["services"]["driver"]["tmpfs"] == ["/run-private:mode=0700"]


def test_bootstrap_keeps_credentials_out_of_artifacts(stack: run.Stack, monkeypatch: pytest.MonkeyPatch) -> None:
    credentials = {"admin_token": "fixture-pat", "client_id": "fixture-id", "client_secret": "fixture-oauth-secret"}
    monkeypatch.setattr(stack, "exec", Mock(return_value=json.dumps(credentials)))

    stack.bootstrap()

    assert stack.credentials["admin_token"] == credentials["admin_token"]
    assert stack.environment["E2E_GITLAB_CLIENT_SECRET"] == credentials["client_secret"]
    assert stack.environment["E2E_STACK_PASSWORD"] == stack.password
    assert not list(stack.directory.iterdir())
    message = " ".join([stack.password, stack.course_token, *credentials.values()])
    assert all(
        value not in stack.sanitized(message) for value in [stack.password, stack.course_token, *credentials.values()]
    )


def test_commands_receive_private_environment(stack: run.Stack, monkeypatch: pytest.MonkeyPatch) -> None:
    execute = Mock(return_value="ready")
    monkeypatch.setattr(run, "command", execute)

    assert stack.command(["docker", "compose", "up"]) == "ready"

    assert execute.call_args.kwargs["env"] is stack.environment


def test_runner_handoff_uses_container_tmpfs(stack: run.Stack, monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock(returncode=0, stdout="fixture-runner-token\n")
    execute = Mock(return_value=response)
    monkeypatch.setattr(run.subprocess, "run", execute)
    register = Mock()
    monkeypatch.setattr(stack, "register_runner", register)
    commands = Mock()
    monkeypatch.setattr(stack, "command", commands)

    stack.register_pending_runner()

    assert execute.call_args.args[0][-2:] == ["cat", "/run-private/runner-token"]
    register.assert_called_once_with("fixture-runner-token")
    assert commands.call_args_list[0].args[0][-2:] == ["rm", "/run-private/runner-token"]
    assert commands.call_args_list[1].args[0][-2:] == ["touch", "/run-private/runner-ready"]
    assert stack.sanitized(response.stdout) == "<redacted>\n"
    assert not list(stack.directory.iterdir())


def test_runner_handoff_waits_until_token_exists(stack: run.Stack, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run.subprocess, "run", Mock(return_value=Mock(returncode=1)))
    register = Mock()
    monkeypatch.setattr(stack, "register_runner", register)

    stack.register_pending_runner()

    register.assert_not_called()
    assert not stack.runner_token
