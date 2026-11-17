import pytest
from pydantic import ValidationError

from manytask.config import ManytaskRmsConfig, ProtectedBranchConfig


def test_protected_branch_config_defaults():
    branch = ProtectedBranchConfig(name="main")

    assert branch.push_access_level == "developer"
    assert branch.merge_access_level == "developer"
    assert branch.allow_force_push is True


def test_protected_branch_config_explicit_values():
    branch = ProtectedBranchConfig(
        name="release",
        push_access_level="maintainer",
        merge_access_level="no_access",
        allow_force_push=False,
    )

    assert branch.push_access_level == "maintainer"
    assert branch.merge_access_level == "no_access"
    assert branch.allow_force_push is False


def test_protected_branch_config_rejects_empty_name():
    with pytest.raises(ValidationError):
        ProtectedBranchConfig(name="")


def test_protected_branch_config_rejects_invalid_access_level():
    with pytest.raises(ValidationError):
        ProtectedBranchConfig(name="main", push_access_level="owner")


def test_rms_config_all_fields_optional():
    rms = ManytaskRmsConfig()

    assert rms.ci_config_path is None
    assert rms.protected_branches is None


def test_rms_config_parses_full_section():
    rms = ManytaskRmsConfig(
        ci_config_path=".gitlab-ci.yml@caos-ami/public-2026",
        protected_branches=[
            {
                "name": "main",
                "push_access_level": "developer",
                "merge_access_level": "developer",
                "allow_force_push": True,
            }
        ],
    )

    assert rms.ci_config_path == ".gitlab-ci.yml@caos-ami/public-2026"
    assert rms.protected_branches[0].name == "main"


def test_rms_config_rejects_duplicate_branch_names():
    with pytest.raises(ValidationError, match="unique"):
        ManytaskRmsConfig(
            protected_branches=[
                {"name": "main"},
                {"name": "main"},
            ]
        )
