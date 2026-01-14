from __future__ import annotations

from pydantic import AnyUrl

from .base import PluginABC, PluginOutput


class CheckGitlabMergeRequestPlugin(PluginABC):
    """Plugin for checking gitlab merge request."""

    name = "check_gitlab_merge_request"

    class Args(PluginABC.Args):
        token: str
        task_dir: str
        repo_url: AnyUrl
        requre_approval: bool = False
        search_for_score: bool = False

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        # TODO: implement
        assert NotImplementedError()

        return PluginOutput(
            output="",
        )


class CollectScoreGitlabMergeRequestPlugin(PluginABC):
    """Plugin for collecting score from gitlab merge request."""

    name = "collect_score_gitlab_merge_request"

    class Args(PluginABC.Args):
        token: str
        task_dir: str
        repo_url: AnyUrl
        requre_approval: bool = False
        search_for_score: bool = False

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        # TODO: implement
        assert NotImplementedError()

        # TODO: implement arithmetical operations in score comment
        # e.g 0.3 + 2*0.7 - 0.2
        # TODO: auto detect percentage or 0-1 score
        # e.g. valid:
        # 0.3 + 2*0.7 - 0.2 = 0.8
        # 30% + 70% - 20% = 80% (return as 0.8)
        # 30 + 70 - 20 = 80 (return as 0.8)

        return PluginOutput(
            output="",
            percentage=1.0,
        )
