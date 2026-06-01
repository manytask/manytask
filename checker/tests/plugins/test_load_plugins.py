import builtins

from checker.plugins import load_plugins


def test_load_plugins_without_pytest(monkeypatch):
    """Plugin discovery must not require pytest to be importable.

    Regression: checker_reporter.py used to live in checker/plugins/ with a
    top-level `import pytest`, so load_plugins() (which exec_module's every
    plugin file) crashed at startup when pytest was absent — breaking checker
    for non-pytest (e.g. C++) courses.
    """
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "pytest" or name.startswith("pytest."):
            raise ModuleNotFoundError("No module named 'pytest'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    plugins = load_plugins()

    assert "run_pytest" in plugins  # pytest *runner* plugin still discovered
