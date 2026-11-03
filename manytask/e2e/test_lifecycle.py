"""Real HTTP/Git/CI test, executed only by the isolated e2e driver container."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import pytest
import requests
import yaml
from bs4 import BeautifulSoup

PAGE_SIZE = 100
PARTIAL_SCORE = 67
FULL_SCORE = 100

pytestmark = pytest.mark.skipif(not os.getenv("E2E_RUN"), reason="Requires the dedicated e2e stack")


class Lifecycle:
    def __init__(self) -> None:
        self.gitlab = os.environ["GITLAB_URL"]
        self.app = os.environ["MANYTASK_URL"]
        self.run = os.environ["E2E_RUN"]
        self.directory = Path("/run-data")
        self.credentials = json.loads((self.directory / "credentials.json").read_text())
        self.redactions = list(self.credentials.values())
        self.api = requests.Session()
        self.api.trust_env = False
        self.api.headers["PRIVATE-TOKEN"] = self.credentials["admin_token"]
        self.evidence: dict[str, Any] = {"run": self.run, "stages": [], "pipelines": []}

    def stage(self, name: str) -> None:
        print(f"[lifecycle] {name}", flush=True)
        self.evidence["stages"].append(name)
        if name.startswith("PASS:"):
            self.evidence["status"] = "passed"
        (self.directory / "result.json").write_text(json.dumps(self.evidence, indent=2))

    def sanitized(self, text: str) -> str:
        for value in self.redactions:
            text = text.replace(value, "<redacted>")
        return re.sub(r'(https?://[^\s?"<>]+)\?[^\s"<>]*', r"\1?<query-redacted>", text)

    def gl(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.api.request(method, f"{self.gitlab}/api/v4/{path}", timeout=180, **kwargs)
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            raise RuntimeError(f"GitLab {method} {path}: {response.status_code}: {self.sanitized(response.text)[:500]}")
        return response.json() if response.content else None

    def wait_app(self) -> None:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                if requests.get(f"{self.app}/healthcheck", timeout=5).status_code == HTTPStatus.OK:
                    return
            except requests.RequestException:
                pass
            time.sleep(3)
        raise TimeoutError("Manytask did not become healthy")

    @staticmethod
    def csrf(response: requests.Response, name: str = "csrf_token") -> str:
        element = BeautifulSoup(response.text, "html.parser").find("input", attrs={"name": name})
        if element is None:
            raise AssertionError(f"Missing {name} input on {response.url.split('?')[0]}")
        return str(element["value"])

    def finish_oauth(self, session: requests.Session, response: requests.Response) -> requests.Response:
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select("a[href]"):
            target = urljoin(response.url, str(anchor["href"]))
            if target.split("?", 1)[0] == f"{self.app}/login_finish":
                return session.get(target, timeout=60)
        form = next(
            (
                form
                for form in soup.find_all("form")
                if urlsplit(str(form.get("action", ""))).path == "/oauth/authorize"
            ),
            None,
        )
        if form is None:
            message = self.sanitized(soup.get_text(" ", strip=True))
            raise AssertionError(f"OAuth authorization did not expose a redirect or consent form: {message[:600]}")
        data = {str(item["name"]): str(item.get("value", "")) for item in form.find_all("input", attrs={"name": True})}
        return session.post(urljoin(response.url, str(form["action"])), data=data, timeout=60)

    def login(self, username: str) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        response = session.get(f"{self.gitlab}/users/sign_in", timeout=30)
        response = session.post(
            f"{self.gitlab}/users/sign_in",
            data={
                "authenticity_token": self.csrf(response, "authenticity_token"),
                "user[login]": username,
                "user[password]": self.credentials["password"],
            },
            timeout=30,
        )
        assert response.status_code == HTTPStatus.OK and "/users/sign_in" not in response.url, "GitLab login failed"
        response = session.get(f"{self.app}/login", timeout=60)
        if "/oauth/authorize" in response.url:
            response = self.finish_oauth(session, response)
        if response.url.rstrip("/") == self.app:
            return session
        assert "/signup_finish" in response.url, "OAuth did not reach registration completion"
        response = session.post(
            f"{self.app}/signup_finish",
            data={"csrf_token": self.csrf(response), "firstname": "Test", "lastname": "Student"},
            timeout=60,
        )
        assert response.status_code == HTTPStatus.OK and response.url.rstrip("/") == self.app, (
            "Manytask registration failed"
        )
        return session

    def create_course(self, teacher: requests.Session) -> None:
        response = teacher.get(f"{self.app}/instance_admin/courses/new", timeout=30)
        response = teacher.post(
            f"{self.app}/instance_admin/courses/new",
            data={
                "csrf_token": self.csrf(response),
                "namespace_id": "0",
                "unique_course_name": "lifecycle",
                "course_group": "lifecycle",
                "course_public_repo": "lifecycle/public",
                "course_students_group": "lifecycle/students",
                "default_branch": "main",
                "registration_secret": "e2e-enroll",
                "token": self.credentials["course_token"],
                "show_allscores": "on",
                "create_private_repo": "on",
                "private_repo_path": "lifecycle/private",
                "use_course_template": "on",
                "template_language": "python",
            },
            timeout=180,
        )
        assert response.status_code == HTTPStatus.OK and "/lifecycle/" in response.url, "Course creation failed"
        self.private = self.gl("GET", "projects/lifecycle%2Fprivate")
        self.public = self.gl("GET", "projects/lifecycle%2Fpublic")
        assert self.private["visibility"] == "private"
        self.evidence["private_project_id"] = self.private["id"]
        self.evidence["public_project_id"] = self.public["id"]

    def file(self, project: int, path: str) -> str:
        result = self.gl("GET", f"projects/{project}/repository/files/{quote(path, safe='')}", params={"ref": "main"})
        return base64.b64decode(result["content"]).decode()

    def configure_teacher_release(self) -> None:
        project = self.private["id"]
        releaser = yaml.safe_load(self.file(project, ".releaser-ci.yml"))
        checker = yaml.safe_load(self.file(project, ".checker.yml"))
        schedule = yaml.safe_load(self.file(project, ".manytask.yml"))
        wheel = next((self.directory / "wheels").glob("*.whl"))
        spec = f".e2e-checker/{wheel.name}"
        self.evidence["checker_wheel_sha256"] = hashlib.sha256(wheel.read_bytes()).hexdigest()
        releaser["variables"]["CHECKER_PIP_SPEC"] = spec
        releaser["variables"]["MANYTASK_URL"] = self.app.removeprefix("http://")
        # The production example uses HTTPS; this isolated, unpublished network uses HTTP.
        releaser["deploy-manytask"]["script"] = [
            line.replace("https://$MANYTASK_API", "http://$MANYTASK_API")
            for line in releaser["deploy-manytask"]["script"]
        ]
        cache = os.getenv("E2E_TOOLCHAIN_IMAGE")
        if cache:
            releaser["verify"]["image"] = cache
            releaser["verify"]["before_script"] = [
                'python3 -m pip install --break-system-packages --force-reinstall --no-deps "$CHECKER_PIP_SPEC"',
                "python3 -m pip check",
            ]
            self.evidence["toolchain_cache_image"] = cache
        checker["testing"]["report_pipeline"] = [
            {
                "name": "Report score to Manytask",
                "run": "report_score_manytask",
                "args": {
                    "username": "${{ env.GITLAB_USER_LOGIN }}",
                    "task_name": "${{ task.task_name }}",
                    "score": "${{ outputs.private_tests.percentage }}",
                    "report_url": f"{self.app}/api/lifecycle/report",
                    "report_token": "${{ env.MANYTASK_TOKEN }}",
                    "check_deadline": True,
                },
            }
        ]
        now = datetime.now(timezone.utc)
        group = schedule["deadlines"]["schedule"][0]
        group["start"] = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        group["end"] = (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
        base = self.file(project, "base.docker")
        if cache:
            base = (
                f"FROM {cache}\n"
                "COPY .e2e-checker /.e2e-checker\n"
                "ARG CHECKER_PIP_SPEC\n"
                'RUN pip3 install --break-system-packages --force-reinstall --no-deps "$CHECKER_PIP_SPEC" '
                "&& pip3 check\n"
            )
        else:
            base = base.replace("ARG CHECKER_PIP_SPEC=", "COPY .e2e-checker /.e2e-checker\nARG CHECKER_PIP_SPEC=")
        actions = [
            {"action": "update", "file_path": path, "content": content}
            for path, content in {
                ".releaser-ci.yml": yaml.safe_dump(releaser, sort_keys=False),
                ".checker.yml": yaml.safe_dump(checker, sort_keys=False),
                ".manytask.yml": yaml.safe_dump(schedule, sort_keys=False),
                "base.docker": base,
            }.items()
        ]
        actions.append(
            {
                "action": "create",
                "file_path": spec,
                "encoding": "base64",
                "content": base64.b64encode(wheel.read_bytes()).decode(),
            }
        )
        self.gl("PUT", f"projects/{project}", json={"ci_config_path": ".releaser-ci.yml"})
        self.gl(
            "POST",
            f"projects/{project}/variables",
            json={"key": "GITLAB_API_TOKEN", "value": self.credentials["admin_token"], "masked": True},
        )
        # Skip the initialization commit's student pipeline; explicitly start the configured release.
        commit = self.gl(
            "POST",
            f"projects/{project}/repository/commits",
            json={
                "branch": "main",
                "commit_message": "Configure isolated lifecycle fixture [skip ci]",
                "actions": actions,
            },
        )
        self.evidence["release_sha"] = commit["id"]

    def save_jobs(self, project: int, pipeline: int) -> list[dict[str, Any]]:
        jobs = self.gl("GET", f"projects/{project}/pipelines/{pipeline}/jobs", params={"per_page": 100})
        for job in jobs:
            response = self.api.get(f"{self.gitlab}/api/v4/projects/{project}/jobs/{job['id']}/trace", timeout=30)
            (self.directory / f"pipeline-{pipeline}-{job['name']}-{job['id']}.log").write_text(
                self.sanitized(response.text)
            )
        return jobs

    def pipeline(self, project: int, sha: str, *, trigger: bool = False) -> int:
        deadline = time.monotonic() + 1200
        pipeline = self.gl("POST", f"projects/{project}/pipeline", json={"ref": "main"}) if trigger else None
        while pipeline is None and time.monotonic() < deadline:
            pipelines = self.gl("GET", f"projects/{project}/pipelines", params={"sha": sha})
            if pipelines:
                pipeline = pipelines[0]
                break
            time.sleep(2)
        assert pipeline is not None, "Push did not create a pipeline"
        identifier = pipeline["id"]
        self.evidence["pipelines"].append({"project": project, "id": identifier, "sha": sha})
        (self.directory / "result.json").write_text(json.dumps(self.evidence, indent=2))
        previous = ""
        while time.monotonic() < deadline:
            if trigger:
                self.cancel_setup_pipelines(project, identifier)
                (self.directory / "result.json").write_text(json.dumps(self.evidence, indent=2))
            pipeline = self.gl("GET", f"projects/{project}/pipelines/{identifier}")
            assert pipeline["sha"] == sha, "Pipeline ran a different commit"
            status = pipeline["status"]
            if status != previous:
                print(f"[pipeline {identifier}] {status}", flush=True)
                previous = status
            if status in {"success", "manual"}:
                self.save_jobs(project, identifier)
                return identifier
            if status in {"failed", "canceled", "skipped"}:
                self.save_jobs(project, identifier)
                raise AssertionError(f"Pipeline {identifier} {status}; see job traces")
            time.sleep(5)
        self.save_jobs(project, identifier)
        raise TimeoutError(f"Pipeline {identifier} exceeded 20 minutes")

    def cancel_setup_pipelines(self, project: int, expected: int) -> None:
        # GitLab can process the initial template push after the fixture updates CI settings.
        # Keep those older configurations from occupying the single disposable runner.
        active = {"created", "pending", "running", "preparing", "waiting_for_resource"}
        for pipeline in self.gl("GET", f"projects/{project}/pipelines", params={"per_page": 100}):
            if pipeline["id"] != expected and pipeline["status"] in active:
                self.gl("POST", f"projects/{project}/pipelines/{pipeline['id']}/cancel")
                self.evidence.setdefault("setup_pipelines_canceled", []).append(pipeline["id"])
                print(f"Canceled setup pipeline {pipeline['id']}; testing pipeline {expected}", flush=True)

    def deploy(self, pipeline: int) -> None:
        project = self.private["id"]
        for name in ["deploy-docker", "deploy-manytask", "deploy-public"]:
            jobs = self.gl("GET", f"projects/{project}/pipelines/{pipeline}/jobs", params={"per_page": 100})
            job = next(job for job in jobs if job["name"] == name)
            if job["status"] == "success":
                continue
            self.gl("POST", f"projects/{project}/jobs/{job['id']}/play")
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                current = self.gl("GET", f"projects/{project}/jobs/{job['id']}")
                if current["status"] == "success":
                    break
                if current["status"] in {"failed", "canceled"}:
                    self.save_jobs(project, pipeline)
                    raise AssertionError(f"{name} failed; see job traces")
                time.sleep(3)
            else:
                raise TimeoutError(f"{name} exceeded five minutes")
            self.stage(f"{name} succeeded")
        self.save_jobs(project, pipeline)
        jobs = self.gl("GET", f"projects/{project}/pipelines/{pipeline}/jobs", params={"per_page": 100})
        assert all(job["status"] == "success" for job in jobs), "Not every releaser job succeeded"
        registry = self.gl("GET", f"projects/{project}/registry/repositories")
        testenv = next(repo for repo in registry if repo["path"].endswith("/testenv-image"))
        tags = {
            tag: self.gl("GET", f"projects/{project}/registry/repositories/{testenv['id']}/tags/{tag}")
            for tag in ["main", "latest"]
        }
        assert tags["main"]["digest"] == tags["latest"]["digest"]
        self.evidence["image_digest"] = tags["latest"]["digest"]

    def inspect_export(self) -> None:
        project = self.public["id"]
        tree = self.gl("GET", f"projects/{project}/repository/tree", params={"recursive": True, "per_page": 100})
        assert len(tree) < PAGE_SIZE, "Export inspection needs pagination"
        paths = [item["path"] for item in tree]
        assert "python/add/add.py" in paths
        assert not any("private" in path or path.startswith((".releaser-ci.yml", ".e2e-checker")) for path in paths)
        stub = self.file(project, "python/add/add.py")
        assert "NotImplementedError" in stub and "return a + b" not in stub
        self.evidence["public_export_sha"] = self.gl("GET", f"projects/{project}/repository/branches/main")["commit"][
            "id"
        ]

    def register_runner(self) -> None:
        runner = self.gl(
            "POST", "user/runners", json={"runner_type": "instance_type", "description": self.run, "run_untagged": True}
        )
        self.redactions.append(runner["token"])
        (self.directory / "runner-token").write_text(runner["token"])
        # Host launcher notices this file and registers the runner on the dedicated daemon.
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if (self.directory / "runner-ready").exists():
                return
            time.sleep(1)
        raise TimeoutError("Launcher did not register the e2e runner")

    def enroll(self) -> requests.Session:
        user = self.gl(
            "POST",
            "users",
            json={
                "username": "student",
                "name": "Test Student",
                "email": "student@example.test",
                "password": self.credentials["password"],
                "skip_confirmation": True,
            },
        )
        token = self.gl(
            "POST",
            f"users/{user['id']}/personal_access_tokens",
            json={
                "name": "e2e-push",
                "scopes": ["write_repository"],
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d"),
            },
        )
        self.student_token = token["token"]
        self.redactions.append(self.student_token)
        student = self.login("student")
        response = student.get(f"{self.app}/lifecycle/create_project", timeout=30)
        response = student.post(
            f"{self.app}/lifecycle/create_project",
            data={"csrf_token": self.csrf(response), "secret": "e2e-enroll"},
            timeout=180,
        )
        assert response.status_code == HTTPStatus.OK and response.url.rstrip("/").endswith("/lifecycle"), (
            "Enrollment failed"
        )
        self.student = self.gl("GET", "projects/lifecycle%2Fstudents%2Fstudent")
        assert self.student["forked_from_project"]["id"] == self.public["id"]
        assert self.student["ci_config_path"] == ".gitlab-ci.yml@lifecycle/public"
        return student

    def push(self, solution: str) -> str:
        repo = self.directory / "student"
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "E2E_GIT_TOKEN": self.student_token}
        askpass = self.directory / "askpass.sh"
        askpass.write_text(
            '#!/bin/sh\ncase "$1" in *Username*) echo oauth2;; *) printf "%s\\n" "$E2E_GIT_TOKEN";; esac\n'
        )
        askpass.chmod(0o700)
        env["GIT_ASKPASS"] = str(askpass)
        commands = []
        if not repo.exists():
            commands.append(["git", "clone", f"{self.gitlab}/lifecycle/students/student.git", str(repo)])
        for args in commands:
            result = subprocess.run(args, env=env, capture_output=True, text=True, check=False)
            assert result.returncode == 0, "Student clone failed"
        (repo / "python/add/add.py").write_text(solution)
        for args in [
            ["git", "add", "python/add/add.py"],
            [
                "git",
                "-c",
                "user.name=Test Student",
                "-c",
                "user.email=student@example.test",
                "commit",
                "-m",
                "Solve add",
            ],
            ["git", "push", "origin", "main"],
        ]:
            result = subprocess.run(args, cwd=repo, env=env, capture_output=True, text=True, check=False)
            assert result.returncode == 0, f"Student {args[1]} failed"
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

    def score(self) -> int:
        response = requests.get(
            f"{self.app}/api/lifecycle/score",
            headers={"Authorization": f"Bearer {self.credentials['course_token']}"},
            data={"username": "student", "task": "add"},
            timeout=30,
        )
        assert response.status_code == HTTPStatus.OK, "Score was not persisted in Manytask"
        payload = response.json()
        assert payload["username"] == "student" and payload["task"] == "add"
        return int(payload["score"])


def test_course_lifecycle() -> None:
    test = Lifecycle()
    test.wait_app()
    test.stage("Fresh database migrations completed; authenticate teacher through OAuth")
    teacher = test.login("root")
    test.stage("Create course and private Python template through the Manytask form")
    test.create_course(teacher)
    test.stage("Configure teacher CI path, reporting, local HTTP endpoints, and checked-out checker wheel")
    test.configure_teacher_release()
    test.register_runner()
    test.stage("Run the real releaser pipeline")
    pipeline = test.pipeline(test.private["id"], test.evidence["release_sha"], trigger=True)
    test.deploy(pipeline)
    test.inspect_export()
    test.stage("Enroll a separate student through Manytask and verify their fork")
    student = test.enroll()
    test.stage("Push a public-test-passing solution that fails a hidden test")
    sha = test.push("def add(a: int, b: int) -> int:\n    return 0 if a < 0 and b < 0 else a + b\n")
    test.pipeline(test.student["id"], sha)
    test.evidence["partial_score"] = test.score()
    assert test.evidence["partial_score"] == PARTIAL_SCORE, "Hidden tests should award two-thirds, not full points"
    test.stage("Push the correct solution and verify persisted full score")
    sha = test.push("def add(a: int, b: int) -> int:\n    return a + b\n")
    test.pipeline(test.student["id"], sha)
    test.evidence["full_score"] = test.score()
    assert test.evidence["full_score"] == FULL_SCORE
    response = student.get(f"{test.app}/lifecycle/", timeout=30)
    assert response.status_code == HTTPStatus.OK
    soup = BeautifulSoup(response.text, "html.parser")
    card = None
    for candidate in soup.select(".mt-task-card"):
        label = candidate.select_one(".mt-card__name")
        if label is not None and label.get_text(strip=True) == "add":
            card = candidate
            break
    assert card is not None, "Task is missing from the student's course page"
    score = card.select_one(".score")
    assert score is not None and score.get_text(strip=True) == "100/100", (
        "Score is missing from the student's course page"
    )
    test.stage("PASS: release → export → student push → hidden tests → Manytask score → course page")
