import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from flask import Flask, render_template
from jinja2 import DictLoader

from manytask import ui
from manytask.web import root_bp


def test_auth_serializer_only_returns_allowed_text_values():
    from manytask.ui_auth import serialize_signup

    app = Flask("auth_test")
    app.secret_key = "test-key"
    app.register_blueprint(root_bp)
    with app.test_request_context(
        "/signup",
        method="POST",
        data={"username": "alice", "firstname": "A", "password": "top-secret", "password2": "top-secret"},
    ):
        data = serialize_signup({"password": "different-secret"})
    assert data["values"] == {"username": "alice", "firstname": "A"}
    assert "secret" not in str(data)


def test_json_cannot_close_script():
    app = Flask("ui_test", template_folder=str(Path(__file__).parents[1] / "manytask/templates"))
    app.secret_key = "test-key"
    name = '</script><script>alert("Имя")</script>'

    with app.test_request_context():
        html = render_template(
            "ui.html",
            payload={"data": {"name": name}, "shared": {"favicon": "/static/favicon.ico"}},
            assets={"js": "/static/dist/app.js", "css": []},
        )

    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.select('script[type="application/json"]')
    assert len(scripts) == 1
    assert json.loads(scripts[0].text)["data"]["name"] == name
    assert not any(
        script.string and 'alert("Имя")' in script.string
        for script in soup.select('script:not([type="application/json"])')
    )


def test_frontend_assets_collects_imported_css_once(tmp_path, monkeypatch):
    manifest = tmp_path / ".vite" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "src/main.tsx": {"file": "assets/main-123.js", "css": ["assets/app-123.css"], "imports": ["_vendor"]},
                "_vendor": {"file": "assets/vendor-123.js", "css": ["assets/app-123.css", "assets/vendor-123.css"]},
            }
        )
    )
    monkeypatch.setattr(ui, "MANIFEST_PATH", manifest)

    assert ui.frontend_assets() == {
        "js": "/static/dist/assets/main-123.js",
        "css": ["/static/dist/assets/app-123.css", "/static/dist/assets/vendor-123.css"],
    }


def test_frontend_assets_missing_manifest_explains_build(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "MANIFEST_PATH", tmp_path / "manifest.json")

    try:
        ui.frontend_assets()
    except RuntimeError as error:
        assert "npm run build" in str(error)
    else:
        raise AssertionError("missing manifest was accepted")


@pytest.mark.parametrize(
    ("template", "page"),
    [
        ("not_ready.html", "not-ready"),
        ("signup.html", "signup"),
        ("signup_yandex_id.html", "signup-yandex-id"),
        ("signup_finish.html", "signup-finish"),
        ("create_project.html", "create-project"),
        ("courses.html", "courses"),
        ("tasks.html", "assignments"),
        ("database.html", "grades"),
        ("create_course.html", "create-course"),
        ("edit_course.html", "edit-course"),
        ("instance_admin_panel.html", "instance-admin"),
        ("namespaces_list.html", "namespaces"),
        ("namespace_panel.html", "namespace"),
    ],
)
def test_all_builtin_pages_use_react(template, page):
    assert ui.PAGE_SERIALIZERS[template][0] == page


@pytest.mark.parametrize(
    ("template", "context", "title"),
    [
        ("courses.html", {}, "Manytask"),
        ("tasks.html", {"course_name": "Python <advanced>"}, "Python <advanced>"),
        ("create_course.html", {}, "Create New Course"),
        ("edit_course.html", {"course": SimpleNamespace(course_name="Python")}, "Edit Course: Python"),
        ("instance_admin_panel.html", {}, "Instance Admin panel"),
        ("namespaces_list.html", {}, "Namespaces"),
        ("namespace_panel.html", {"namespace": SimpleNamespace(name="School")}, "School - Namespace Panel"),
    ],
)
def test_shell_preserves_page_metadata(template, context, title, monkeypatch):
    app = Flask("metadata_test", template_folder=str(Path(__file__).parents[1] / "manytask/templates"))
    # These contracts isolate the shell from the domain serializers, tested separately.
    page, _ = ui.PAGE_SERIALIZERS[template]
    monkeypatch.setitem(ui.PAGE_SERIALIZERS, template, (page, lambda context: {}))
    monkeypatch.setattr(ui, "serialize_shared", lambda context: {"favicon": "/static/course.ico"})
    monkeypatch.setattr(ui, "frontend_assets", lambda: {"js": "/static/dist/main.js", "css": []})
    with app.test_request_context():
        soup = BeautifulSoup(ui.render_ui(template, **context), "html.parser")
    assert soup.title is not None
    assert soup.title.text == title
    assert soup.select_one('link[rel="icon"]')["href"] == "/static/course.ico"
    assert soup.select_one('meta[name="robots"]')["content"] == "noindex"


def test_external_template_keeps_jinja_fallback():
    app = Flask("external_test")
    app.jinja_loader = DictLoader({"external.html": "Integration: {{ name }}"})
    with app.test_request_context():
        assert ui.render_ui("external.html", name="<user>") == "Integration: &lt;user&gt;"


def test_frontend_assets_recurses_shared_css_and_cycles(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "src/main.tsx": {"file": "assets/main.js", "imports": ["_one", "_two"]},
                "_one": {"file": "assets/one.js", "css": ["assets/one.css"], "imports": ["_two"]},
                "_two": {"file": "assets/two.js", "css": ["assets/two.css", "assets/one.css"], "imports": ["_one"]},
            }
        )
    )
    monkeypatch.setattr(ui, "MANIFEST_PATH", manifest)
    assert ui.frontend_assets() == {
        "js": "/static/dist/assets/main.js",
        "css": ["/static/dist/assets/one.css", "/static/dist/assets/two.css"],
    }


@pytest.mark.parametrize("entry", [{"imports": ["_missing"]}, {"file": "main.js", "imports": ["_missing"]}])
def test_frontend_assets_invalid_chunk_explains_build(tmp_path, monkeypatch, entry):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"src/main.tsx": entry}))
    monkeypatch.setattr(ui, "MANIFEST_PATH", manifest)
    with pytest.raises(RuntimeError, match="npm run build"):
        ui.frontend_assets()
