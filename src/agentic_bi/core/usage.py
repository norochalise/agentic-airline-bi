"""Token usage, estimated cost and model latency for one agent run."""

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from agentic_bi.config import openai_prices


@dataclass
class ModelCall:
    """One Responses API call: its stage, latency and token counts."""

    stage: str
    seconds: float
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0


def _count(value: Any) -> int:
    return value if isinstance(value, int) else 0


def read_usage(response: Any) -> tuple[int, int, int]:
    """Return (input, cached input, output) tokens; 0 when not reported."""

    usage = getattr(response, "usage", None)

    if usage is None:
        return 0, 0, 0

    details = getattr(usage, "input_tokens_details", None)

    return (
        _count(getattr(usage, "input_tokens", 0)),
        _count(getattr(details, "cached_tokens", 0)),
        _count(getattr(usage, "output_tokens", 0)),
    )


def estimate_cost(
    input_tokens: int, cached_tokens: int, output_tokens: int
) -> float | None:
    """Estimated USD cost from the configured prices; None when unset."""

    prices = openai_prices()

    if prices is None:
        return None

    input_price, cached_price, output_price = prices

    cost = (
        (input_tokens - cached_tokens) * input_price
        + cached_tokens * cached_price
        + output_tokens * output_price
    ) / 1_000_000

    return round(cost, 6)


@dataclass
class UsageMeter:
    """Records every model call made during one run, grouped by stage."""

    stage: str = "agent"
    calls: list[ModelCall] = field(default_factory=list)

    def summary(self, *, tool_seconds: float, total_seconds: float | None) -> dict:
        input_tokens = sum(call.input_tokens for call in self.calls)
        cached_tokens = sum(call.cached_tokens for call in self.calls)
        output_tokens = sum(call.output_tokens for call in self.calls)

        stages: dict[str, dict[str, Any]] = {}

        for call in self.calls:
            stage = stages.setdefault(
                call.stage,
                {
                    "stage": call.stage,
                    "calls": 0,
                    "seconds": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                },
            )
            stage["calls"] += 1
            stage["seconds"] += call.seconds
            stage["input_tokens"] += call.input_tokens
            stage["output_tokens"] += call.output_tokens

        for stage in stages.values():
            stage["seconds"] = round(stage["seconds"], 3)

        return {
            "model_calls": len(self.calls),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost_usd": estimate_cost(
                input_tokens, cached_tokens, output_tokens
            ),
            "duration_seconds": (
                round(total_seconds, 3) if total_seconds is not None else None
            ),
            "model_seconds": round(sum(call.seconds for call in self.calls), 3),
            "tool_seconds": round(tool_seconds, 3),
            "stages": list(stages.values()),
        }


class _MeteredResponses:
    def __init__(self, responses: Any, meter: UsageMeter) -> None:
        self._responses = responses
        self._meter = meter

    def create(self, **kwargs: Any) -> Any:
        started = perf_counter()

        response = self._responses.create(**kwargs)

        input_tokens, cached_tokens, output_tokens = read_usage(response)

        self._meter.calls.append(
            ModelCall(
                stage=self._meter.stage,
                seconds=perf_counter() - started,
                input_tokens=input_tokens,
                cached_tokens=cached_tokens,
                output_tokens=output_tokens,
            )
        )

        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._responses, name)


class MeteredClient:
    """
    Wraps an OpenAI client so every `responses.create` call is timed and
    its token usage recorded; everything else passes straight through.
    """

    def __init__(self, client: Any, meter: UsageMeter) -> None:
        self._client = client
        self.responses = _MeteredResponses(client.responses, meter)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)
