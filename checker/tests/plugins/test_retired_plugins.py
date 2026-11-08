import pytest

from checker.configs import PipelineStageConfig
from checker.exceptions import BadConfig
from checker.pipeline import PipelineRunner
from checker.plugins import load_plugins


@pytest.mark.parametrize(
    "plugin_name",
    ["check_gitlab_merge_request", "collect_score_gitlab_merge_request"],
)
def test_retired_mr_plugins_reject_pipeline(plugin_name: str) -> None:
    """Unimplemented MR checks must not silently award full credit."""
    plugins = load_plugins()
    stage = PipelineStageConfig(name="Review submission", run=plugin_name)

    with pytest.raises(BadConfig, match=f"Unknown plugin {plugin_name}"):
        PipelineRunner(pipeline=[stage], plugins=plugins)
