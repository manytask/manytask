from __future__ import annotations

from typing import Literal, Union

from checker.exceptions import PluginExecutionFailed

from .base import PluginABC, PluginOutput


class AggregatePlugin(PluginABC):
    """Given scores and optional weights and strategy, aggregate them, return the score."""

    name = "aggregate"

    class Args(PluginABC.Args):
        scores: list[float]
        weights: Union[list[float], None] = None  # as pydantic does not support | in older python versions
        strategy: Literal["mean", "sum", "min", "max", "product"] = "mean"
        # TODO: validate for weights: len weights should be equal to len scores
        # TODO: validate not empty scores

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        weights = args.weights or ([1.0] * len(args.scores))

        if len(args.scores) != len(weights):
            raise PluginExecutionFailed(
                f"Length of scores ({len(args.scores)}) and weights ({len(weights)}) does not match",
                output=f"Length of scores ({len(args.scores)}) and weights ({len(weights)}) does not match",
            )

        if len(args.scores) == 0 or len(weights) == 0:
            raise PluginExecutionFailed(
                f"Length of scores ({len(args.scores)}) or weights ({len(weights)}) is zero",
                output=f"Length of scores ({len(args.scores)}) or weights ({len(weights)}) is zero",
            )

        weighted_scores = [score * weight for score, weight in zip(args.scores, weights)]

        if args.strategy == "mean":
            score = sum(weighted_scores) / len(weighted_scores)
        elif args.strategy == "sum":
            score = sum(weighted_scores)
        elif args.strategy == "min":
            score = min(weighted_scores)
        elif args.strategy == "max":
            score = max(weighted_scores)
        elif args.strategy == "product":
            from functools import reduce

            score = reduce(lambda x, y: x * y, weighted_scores)
        else:  # pragma: no cover
            assert False, "Not reachable"

        return PluginOutput(
            output=(
                f"Get scores:  {args.scores}\n"
                f"Get weights: {args.weights}\n"
                f"Aggregate weighted scores {weighted_scores} with strategy {args.strategy}\n"
                f"Score: {score:.2f}"
            ),
            percentage=score,
        )
