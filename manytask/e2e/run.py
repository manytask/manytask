"""Launch the real lifecycle suite on an explicitly selected, empty Docker daemon."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import secrets
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

COMPONENT = Path(__file__).resolve().parents[1]
REPOSITORY = COMPONENT.parent


class CommandFailed(RuntimeError):
    def __init__(self, args: list[str], result: subprocess.CompletedProcess[str]) -> None:
        super().__init__(f"{args[0]} {args[1]} failed (exit {result.returncode})")
        self.output = result.stdout + result.stderr


def command(args: list[str], *, stdin: str | None = None, timeout: int = 1200) -> str:
    result = subprocess.run(args, input=stdin, text=True, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        # Commands can return freshly generated tokens. Never echo raw output here.
        raise CommandFailed(args, result)
    return result.stdout


class Stack:
    def __init__(self, docker_host: str, toolchain_image: str = "", build_timeout: int = 3600) -> None:
        self.docker = ["docker", "--host", docker_host]
        self.toolchain_image = toolchain_image
        self.build_timeout = build_timeout
        self.project = f"manytask-e2e-{secrets.token_hex(5)}"
        artifacts = COMPONENT / ".tmp" / "e2e"
        artifacts.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix=f"{self.project}-", dir=artifacts))
        self.directory.chmod(0o700)
        self.network = f"{self.project}-net"
        self.compose = self.docker + [
            "compose",
            "--project-name",
            self.project,
            "--env-file",
            str(self.directory / "empty.env"),
            "--file",
            str(self.directory / "compose.yml"),
        ]
        self.password = f"E2e-{secrets.token_hex(16)}!"
        self.course_token = secrets.token_hex(24)
        self.network_created = False
        self.compose_created = False

    def prepare(self) -> None:
        if command(self.docker + ["ps", "-aq"]).strip():
            raise RuntimeError("Refusing to run: the selected daemon already has containers. Use a dedicated daemon.")
        info = json.loads(command(self.docker + ["info", "--format", "{{json .}} "]))
        if info["MemTotal"] < 7 * 1024**3:
            raise RuntimeError("The dedicated Docker daemon needs at least 8 GB RAM.")
        subnet_prefix = f"172.28.{secrets.randbelow(250)}"
        command(
            self.docker
            + [
                "network",
                "create",
                "--subnet",
                f"{subnet_prefix}.0/24",
                "--gateway",
                f"{subnet_prefix}.1",
                "--label",
                f"org.manytask.e2e.run={self.project}",
                self.network,
            ]
        )
        self.network_created = True
        network = json.loads(command(self.docker + ["network", "inspect", self.network]))[0]
        self.gitlab_ip = str(ipaddress.ip_address(network["IPAM"]["Config"][0]["Gateway"]) + 253)
        self.gitlab_url = f"http://{self.gitlab_ip}:8929"
        self.registry = f"{self.gitlab_ip}:5050"
        command(["uv", "build", "--wheel", "--out-dir", str(self.directory / "wheels"), str(REPOSITORY / "checker")])
        context = self.directory / "context"
        (context / "manytask").mkdir(parents=True)
        for name in ["Dockerfile", "pyproject.toml", "uv.lock", "VERSION"]:
            shutil.copyfile(COMPONENT / name, context / "manytask" / name)
        for source, destination in [
            (COMPONENT / "manytask", context / "manytask" / "manytask"),
            (REPOSITORY / "course-template", context / "course-template"),
        ]:
            shutil.copytree(
                source,
                destination,
                ignore=shutil.ignore_patterns(".env*", ".git", ".venv", "__pycache__", ".tmp"),
            )
        (self.directory / "empty.env").write_text("")
        (self.directory / "app.env").write_text("")
        config = self.configuration()
        (self.directory / "compose.yml").write_text(yaml.safe_dump(config, sort_keys=False))
        self.compose_created = True
        self.write_manifest({"project": self.project, "gitlab_url": self.gitlab_url, "status": "starting"})

    def configuration(self) -> dict[str, Any]:
        gitlab_config = f"""
external_url '{self.gitlab_url}'
registry_external_url 'http://{self.registry}'
prometheus_monitoring['enable'] = false
alertmanager['enable'] = false
gitlab_kas['enable'] = false
puma['worker_processes'] = 0
sidekiq['concurrency'] = 5
gitlab_rails['initial_root_password'] = ENV['GITLAB_ROOT_PASSWORD']
"""
        return {
            "services": {
                "postgres": {
                    "image": "postgres:17",
                    "environment": {
                        "POSTGRES_USER": "manytask",
                        "POSTGRES_DB": "manytask",
                        "POSTGRES_PASSWORD": self.password,
                    },
                    "command": ["postgres", "-c", "max_locks_per_transaction=256"],
                    "volumes": ["postgres:/var/lib/postgresql/data"],
                    "healthcheck": {"test": ["CMD-SHELL", "pg_isready -U manytask"], "interval": "3s"},
                },
                "gitlab": {
                    "image": "gitlab/gitlab-ce:latest",
                    "shm_size": "256m",
                    "environment": {"GITLAB_ROOT_PASSWORD": self.password, "GITLAB_OMNIBUS_CONFIG": gitlab_config},
                    "networks": {"default": {"ipv4_address": self.gitlab_ip}},
                    "volumes": [
                        "gitlab-config:/etc/gitlab",
                        "gitlab-data:/var/opt/gitlab",
                        "gitlab-logs:/var/log/gitlab",
                    ],
                },
                "manytask": {
                    "build": {
                        "context": str(self.directory / "context"),
                        "dockerfile": "manytask/Dockerfile",
                        "target": "app",
                    },
                    "env_file": [str(self.directory / "app.env")],
                    "volumes": ["app-cache:/cache"],
                    "command": [
                        "gunicorn",
                        "--bind",
                        "0.0.0.0:5050",
                        "--workers",
                        "1",
                        "--timeout",
                        "180",
                        "manytask:create_app()",
                    ],
                    "depends_on": {"postgres": {"condition": "service_healthy"}},
                },
                "runner": {
                    "image": "gitlab/gitlab-runner:alpine",
                    "volumes": ["runner:/etc/gitlab-runner", "/var/run/docker.sock:/var/run/docker.sock"],
                },
                "driver": {
                    "build": {"context": str(COMPONENT / "e2e")},
                    "environment": {
                        "GITLAB_URL": self.gitlab_url,
                        "MANYTASK_URL": "http://manytask:5050",
                        "E2E_RUN": self.project,
                        "E2E_TOOLCHAIN_IMAGE": self.toolchain_image,
                        "PYTHONUNBUFFERED": "1",
                    },
                    "volumes": [f"{COMPONENT / 'e2e'}:/suite:ro", f"{self.directory}:/run-data"],
                    "working_dir": "/suite",
                    "command": ["pytest", "-q", "-s", "--tb=short", "-p", "no:cacheprovider", "test_lifecycle.py"],
                },
            },
            "networks": {"default": {"external": True, "name": self.network}},
            "volumes": {
                name: {} for name in ["postgres", "gitlab-config", "gitlab-data", "gitlab-logs", "runner", "app-cache"]
            },
        }

    def write_manifest(self, content: dict[str, Any]) -> None:
        (self.directory / "result.json").write_text(json.dumps(content, indent=2) + "\n")

    def exec(self, service: str, args: list[str], *, stdin: str | None = None) -> str:
        return command(self.compose + ["exec", "-T", service, *args], stdin=stdin)

    def wait_gitlab(self) -> None:
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            result = subprocess.run(
                self.compose + ["exec", "-T", "gitlab", "curl", "-fsS", "http://127.0.0.1:8929/-/readiness"],
                capture_output=True,
                timeout=20,
                check=False,
            )
            if result.returncode == 0:
                return
            print("Waiting for fresh GitLab to finish initialization…", flush=True)
            time.sleep(15)
        raise TimeoutError("Fresh GitLab was not ready within 15 minutes")

    def bootstrap(self) -> None:
        script = """
require 'json'
user = User.find_by_username!('root')
pat = user.personal_access_tokens.create!(
  name: 'e2e-admin', scopes: [:api, :read_user, :write_repository], expires_at: 1.day.from_now
)
pat.set_token(SecureRandom.hex(32)); pat.save!
app = Doorkeeper::Application.create!(
  name: 'manytask-e2e', redirect_uri: 'http://manytask:5050/login_finish',
  scopes: 'openid email profile read_user', confidential: true, trusted: true,
  organization_id: Organizations::Organization.default_organization.id
)
ApplicationSetting.current.update!(require_admin_approval_after_user_signup: false)
puts({admin_token: pat.token, client_id: app.uid, client_secret: app.secret}.to_json)
"""
        output = self.exec("gitlab", ["gitlab-rails", "runner", "-"], stdin=script)
        credentials = json.loads(
            next(line for line in reversed(output.splitlines()) if line.startswith('{"admin_token"'))
        )
        credentials |= {"password": self.password, "course_token": self.course_token}
        # Test-only plaintext handoff to the driver; see the credential policy in e2e/README.md.
        path = self.directory / "credentials.json"
        path.write_text(json.dumps(credentials))
        path.chmod(0o600)
        environment = {
            "DATABASE_URL": f"postgresql://manytask:{self.password}@postgres/manytask",
            "INITIAL_INSTANCE_ADMIN": "root",
            "APPLY_MIGRATIONS": "true",
            "FLASK_SECRET_KEY": secrets.token_hex(32),
            "RMS": "gitlab",
            "GITLAB_URL": self.gitlab_url,
            "GITLAB_OAUTH_URL": self.gitlab_url,
            "GITLAB_ADMIN_TOKEN": credentials["admin_token"],
            "GITLAB_CLIENT_ID": credentials["client_id"],
            "GITLAB_CLIENT_SECRET": credentials["client_secret"],
        }
        # Intentional test-only plaintext for Compose: private 0700 directory, 0600 file,
        # deleted by default cleanup. --keep-on-failure retains it for debugging (see e2e/README.md).
        path = self.directory / "app.env"
        path.write_text("".join(f"{key}={value}\n" for key, value in environment.items()))
        path.chmod(0o600)

    def register_runner(self, token: str) -> None:
        self.exec(
            "runner",
            [
                "gitlab-runner",
                "register",
                "--non-interactive",
                "--url",
                self.gitlab_url,
                "--token",
                token,
                "--executor",
                "docker",
                "--docker-image",
                "alpine:3.20",
                "--docker-network-mode",
                self.network,
                "--docker-volumes",
                "/var/run/docker.sock:/var/run/docker.sock",
                "--docker-pull-policy",
                "if-not-present",
                "--docker-disable-cache",
                "--docker-container-labels",
                f"org.manytask.e2e.run:{self.project}",
                "--clone-url",
                self.gitlab_url,
            ],
        )

    def run(self) -> None:
        print(f"Isolated test project: {self.project}\nArtifacts: {self.directory}", flush=True)
        self.prepare()
        print("Building the checked-out Manytask and test driver before starting services.", flush=True)
        command(self.compose + ["build", "manytask", "driver"], timeout=self.build_timeout)
        print("Starting fresh GitLab and Postgres (no host ports or development mounts).", flush=True)
        command(self.compose + ["up", "-d", "gitlab", "postgres", "runner"])
        self.wait_gitlab()
        self.bootstrap()
        print("Starting Manytask and applying migrations.", flush=True)
        command(self.compose + ["up", "-d", "--no-build", "manytask"])
        # Stream only the test's intentionally sanitized output.
        process = subprocess.Popen(self.compose + ["run", "--rm", "driver"])
        deadline = time.monotonic() + 2700
        while process.poll() is None:
            token_path = self.directory / "runner-token"
            if token_path.exists() and not (self.directory / "runner-ready").exists():
                token = token_path.read_text()
                self.register_runner(token)
                token_path.unlink()
                (self.directory / "runner-ready").touch()
            if time.monotonic() > deadline:
                process.terminate()
                process.wait(timeout=30)
                raise TimeoutError("Lifecycle exceeded 45 minutes")
            time.sleep(1)
        if process.returncode:
            raise RuntimeError("Lifecycle test failed; see the sanitized artifacts")

    def cleanup(self) -> None:
        errors = []

        def attempt(args: list[str]) -> str:
            try:
                return command(args)
            except (RuntimeError, subprocess.TimeoutExpired) as error:
                errors.append(type(error).__name__)
                return ""

        if self.compose_created:
            redactions = [self.password, self.course_token]
            credentials = self.directory / "credentials.json"
            if credentials.exists():
                redactions += list(json.loads(credentials.read_text()).values())
            logs = attempt(self.compose + ["logs", "--no-color", "--tail", "300"])
            for value in redactions:
                if value:
                    logs = logs.replace(value, "<redacted>")
            logs = re.sub(r"([?&](?:code|token|access_token|client_secret)=)[^\s&\"<>]+", r"\1<redacted>", logs)
            (self.directory / "services.log").write_text(logs)
            jobs = attempt(self.docker + ["ps", "-aq", "--filter", f"label=org.manytask.e2e.run={self.project}"])
            if jobs.strip():
                attempt(self.docker + ["rm", "-f", *jobs.split()])
            attempt(self.compose + ["down", "--volumes", "--remove-orphans", "--timeout", "30"])
        if self.network_created:
            attempt(self.docker + ["network", "rm", self.network])
        for name in ["credentials.json", "app.env", "compose.yml", "runner-token", "askpass.sh"]:
            (self.directory / name).unlink(missing_ok=True)
        (self.directory / "cleanup.json").write_text(json.dumps({"project": self.project, "errors": errors}))
        if errors:
            raise RuntimeError("Test cleanup was incomplete; inspect the dedicated daemon before reusing it")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docker-host", required=True, help="Socket of a dedicated, empty daemon; never your dev daemon"
    )
    parser.add_argument(
        "--keep-on-failure", action="store_true", help="Keep only the isolated test stack for debugging"
    )
    parser.add_argument(
        "--toolchain-image", default="", help="Optional preloaded toolchain image for dependency caching"
    )
    parser.add_argument(
        "--build-timeout", type=int, default=3600, help="Image build timeout in seconds (default: 3600)"
    )
    args = parser.parse_args()
    if args.build_timeout <= 0:
        parser.error("--build-timeout must be positive")

    def interrupt(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt("Lifecycle interrupted; cleaning up its isolated stack")

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    stack = Stack(args.docker_host, args.toolchain_image, args.build_timeout)
    failed = False
    try:
        stack.run()
    except BaseException as error:
        failed = True
        result_path = stack.directory / "result.json"
        evidence = json.loads(result_path.read_text()) if result_path.exists() else {"project": stack.project}
        evidence.update(status="failed", failure_type=type(error).__name__)
        stack.write_manifest(evidence)
        if isinstance(error, (CommandFailed, subprocess.TimeoutExpired)):
            parts = (error.output,) if isinstance(error, CommandFailed) else (error.stdout, error.stderr)
            output = "".join(part.decode(errors="replace") if isinstance(part, bytes) else part or "" for part in parts)
            output = output.replace(stack.password, "<redacted>").replace(stack.course_token, "<redacted>")
            output = re.sub(r"[a-fA-F0-9]{32,}|glpat-[\w-]+", "<redacted>", output)
            (stack.directory / "command-error.log").write_text(output)
            print(output[-6000:], flush=True)
        raise
    finally:
        if failed and args.keep_on_failure:
            print(f"Kept isolated test stack for debugging: {stack.directory}", flush=True)
        else:
            stack.cleanup()


if __name__ == "__main__":
    main()
