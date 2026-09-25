"""Test task URL template with $USER_NAME macro."""

import pytest
from flask import Flask, render_template_string

from manytask.config import ManytaskUiConfig


def test_task_url_template_with_user_name():
    """Test that $USER_NAME macro is properly replaced in task URL template."""
    # Create a simple Jinja2 template that mimics the actual template logic
    template = """
    {% set task_link = task_url_template | replace('$GROUP_NAME', group_name) |
      replace('$TASK_NAME', task_name) | replace('$USER_NAME', username) %}
    {{ task_link }}
    """

    app = Flask(__name__)

    with app.app_context():
        # Test with all macros present
        result = render_template_string(
            template,
            task_url_template="https://gitlab.example.com/$GROUP_NAME/$USER_NAME/$TASK_NAME",
            group_name="homework01",
            task_name="task1",
            username="student123",
        )
        assert result.strip() == "https://gitlab.example.com/homework01/student123/task1"

        # Test with only $USER_NAME and $TASK_NAME
        result = render_template_string(
            template,
            task_url_template="https://gitlab.example.com/students/$USER_NAME/$TASK_NAME",
            group_name="homework01",
            task_name="task2",
            username="student456",
        )
        assert result.strip() == "https://gitlab.example.com/students/student456/task2"

        # Test with special characters in username
        result = render_template_string(
            template,
            task_url_template="https://gitlab.example.com/$GROUP_NAME/$USER_NAME/$TASK_NAME",
            group_name="hw",
            task_name="task",
            username="john-doe_123",
        )
        assert result.strip() == "https://gitlab.example.com/hw/john-doe_123/task"


def test_ui_config_accepts_user_name_macro():
    """Test that ManytaskUiConfig accepts templates with $USER_NAME macro."""
    # Test valid template with all macros
    config = ManytaskUiConfig(task_url_template="https://gitlab.com/$GROUP_NAME/$USER_NAME/$TASK_NAME")
    assert "$USER_NAME" in config.task_url_template

    # Test valid template with only $USER_NAME
    config = ManytaskUiConfig(task_url_template="https://gitlab.com/students/$USER_NAME/tasks")
    assert "$USER_NAME" in config.task_url_template

    # Test that validator still works for invalid URLs
    with pytest.raises(ValueError, match="task_url_template should be http or https"):
        ManytaskUiConfig(task_url_template="ftp://example.com/$USER_NAME")


def test_task_url_template_order_independence():
    """Test that macro replacement order doesn't matter."""
    template = """
    {% set task_link = task_url_template | replace('$GROUP_NAME', group_name) | 
    replace('$TASK_NAME', task_name) | replace('$USER_NAME', username) %}
    {{ task_link }}
    """

    app = Flask(__name__)

    with app.app_context():
        # Different order of macros in template
        templates = [
            "https://gitlab.com/$USER_NAME/$GROUP_NAME/$TASK_NAME",
            "https://gitlab.com/$TASK_NAME/$USER_NAME/$GROUP_NAME",
            "https://gitlab.com/$GROUP_NAME/$TASK_NAME/$USER_NAME",
        ]

        expected = [
            "https://gitlab.com/student/hw01/task1",
            "https://gitlab.com/task1/student/hw01",
            "https://gitlab.com/hw01/task1/student",
        ]

        for tmpl, exp in zip(templates, expected):
            result = render_template_string(
                template, task_url_template=tmpl, group_name="hw01", task_name="task1", username="student"
            )
            assert result.strip() == exp


def test_task_url_template_partial_macros():
    """Test templates with only some macros present."""
    template = """
    {% set task_link = task_url_template | replace('$GROUP_NAME', group_name) | 
    replace('$TASK_NAME', task_name) | replace('$USER_NAME', username) %}
    {{ task_link }}
    """

    app = Flask(__name__)

    with app.app_context():
        # Template with only $USER_NAME
        result = render_template_string(
            template,
            task_url_template="https://gitlab.com/$USER_NAME/all-tasks",
            group_name="hw01",
            task_name="task1",
            username="student",
        )
        assert result.strip() == "https://gitlab.com/student/all-tasks"

        # Template with no macros (static URL)
        result = render_template_string(
            template,
            task_url_template="https://gitlab.com/static/url",
            group_name="hw01",
            task_name="task1",
            username="student",
        )
        assert result.strip() == "https://gitlab.com/static/url"
