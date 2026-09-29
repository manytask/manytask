import json
from pathlib import Path

from bs4 import BeautifulSoup
from flask import Flask, render_template

from manytask import ui


def test_json_cannot_close_script():
    app = Flask("ui_test", template_folder=str(Path(__file__).parents[1] / "manytask/templates"))
    app.secret_key = "test-key"
    name = '</script><script>alert("Имя")</script>'

    with app.test_request_context():
        html = render_template(
            "ui.html",
            payload={"data": {"name": name}},
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
