"""Compatibility checks for configuring the disposable course release fixture."""

import copy
import subprocess

from e2e.test_lifecycle import configure_buildkit_registry


def test_docker_releaser_is_unchanged() -> None:
    releaser = {".docker": {"before_script": ["docker info"]}}
    original = copy.deepcopy(releaser)

    configure_buildkit_registry(releaser)

    assert releaser == original


def test_buildkit_uses_isolated_http_registry() -> None:
    releaser = {
        ".buildkit": {
            "before_script": ["echo configure registry credentials"],
            "variables": {"BUILDKITD_FLAGS": "--oci-worker-no-process-sandbox"},
        }
    }

    configure_buildkit_registry(releaser)

    buildkit = releaser[".buildkit"]
    assert buildkit["before_script"][0] == "echo configure registry credentials"
    assert buildkit["variables"]["BUILDKITD_FLAGS"] == (
        "--oci-worker-no-process-sandbox --config=/home/user/buildkitd.toml"
    )
    script = buildkit["before_script"][-1]
    result = subprocess.run(
        ["sh", "-c", script.split(" > ")[0]],
        env={"CI_REGISTRY": "172.28.1.254:5050"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == '[registry."172.28.1.254:5050"]\n  http = true\n'
