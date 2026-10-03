"""Bounded, tool-using BI agent for one user question.

run_agent() is a short pipeline:

    interaction_gate   classify the question; answer early exits directly
    choose_skill       map the intent (or keywords) to a skill
    run_tool_loop      model <-> tools, under budgets and guards
    finish_run         final checkpoint, trace and AgentResult

Each tool call goes through handle_tool_call (guards) and execute_tool
(access policy -> retry -> output validation).
"""

import json
import logging
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from agentic_bi.config import MAX_STEPS, MAX_TOOL_CALLS, openai_model
from agentic_bi.core.action_guard import enforce_action_policy
from agentic_bi.core.checkpoint import create_checkpoint
from agentic_bi.core.clients import get_openai_client
from agentic_bi.core.followup import condense_question
from agentic_bi.core.interaction import classify_interaction
from agentic_bi.core.interaction_response import build_interaction_response
from agentic_bi.core.observability import (
    AgentTrace,
    ExecutionTimer,
    add_event,
    create_trace,
    finish_trace,
)
from agentic_bi.core.prompts import (
    build_agent_instructions,
    build_final_answer_instructions,
)
from agentic_bi.core.reliability import execute_with_retry
from agentic_bi.core.run_store import RunStore, default_run_store
from agentic_bi.core.state import AgentState
from agentic_bi.core.usage import MeteredClient, UsageMeter
from agentic_bi.skills.loader import load_skill
from agentic_bi.skills.router import select_skill
from agentic_bi.tools.delta_current_info import answer_current_delta_question
from agentic_bi.tools.registry import (
    DATA_ANALYSIS_TOOL,
    DELAY_CAUSES_TOOL,
    KNOWLEDGE_SEARCH_TOOL,
    PERFORMANCE_TOOL,
    TOOL_REGISTRY,
    WEB_SEARCH_TOOL,
    ToolSpec,
    get_tool_specs_for_skill,
)

logger = logging.getLogger(__name__)

INTENT_TO_SKILL = {
    "airline_knowledge": "knowledge-analysis",
    "airline_data": "data-analysis",
}

# When one of these tools has used its per-run budget, the next model
# call is forced to write the final answer.
FINAL_ANSWER_TRIGGERS = {
    "knowledge-analysis": (KNOWLEDGE_SEARCH_TOOL, WEB_SEARCH_TOOL),
    "data-analysis": (DATA_ANALYSIS_TOOL, PERFORMANCE_TOOL, DELAY_CAUSES_TOOL),
}

# Names used in stop reasons and guard events for per-tool budgets.
BUDGET_LABELS = {
    KNOWLEDGE_SEARCH_TOOL: "knowledge_search",
    DATA_ANALYSIS_TOOL: "data_analysis",
    WEB_SEARCH_TOOL: "web_search",
}

DATASET_TITLE = "Delta-marketed domestic flight data — July 2026"


@dataclass
class AgentResult:
    goal: str
    selected_skill: str | None
    final_answer: str
    stop_reason: str | None
    step_count: int
    tool_call_count: int
    knowledge_search_count: int
    data_analysis_count: int

    web_search_count: int = 0

    sources: list[dict[str, Any]] = field(default_factory=list)

    tool_history: list[dict[str, Any]] = field(default_factory=list)

    observations: list[dict[str, Any]] = field(default_factory=list)

    errors: list[dict[str, Any]] = field(default_factory=list)

    trace: AgentTrace | None = None

    # Tokens, estimated cost and model/tool time (see core/usage.py).
    usage: dict[str, Any] | None = None


# -------------------------------------------------------------------
# Tool execution
# -------------------------------------------------------------------


class ToolCallError(Exception):
    """A tool call failed; the model is told why and may correct itself."""

    def __init__(
        self,
        error_type: str,
        message: str,
        *,
        details: Any = None,
        error: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.details = details
        self.error = error

    def model_output(self) -> str:
        """JSON returned to the model as the tool output."""

        payload = {
            "status": "error",
            "error_type": self.error_type,
            "message": self.message,
        }

        if self.details is not None:
            payload["details"] = self.details

        return json.dumps(payload)


def parse_arguments(spec: ToolSpec, raw_arguments: str) -> dict[str, Any]:
    """Parse the model's JSON arguments and validate them against the spec."""

    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise ToolCallError(
            "argument_parse_error",
            "Tool arguments were not valid JSON.",
            error=str(exc),
        ) from exc

    try:
        return spec.input_model.model_validate(arguments).model_dump()
    except ValidationError as exc:
        raise ToolCallError(
            "input_validation_error",
            "Tool arguments failed validation.",
            details=json.loads(exc.json()),
        ) from exc


def execute_tool(
    spec: ToolSpec, arguments: dict[str, Any], *, approved: bool = False
) -> dict[str, Any]:
    """
    Run one validated tool call: access policy, retries, output validation.

    Raises ToolCallError when the output breaks the tool's contract; any
    other exception is a tool execution failure.
    """

    enforce_action_policy(spec.name, approved=approved, registry={spec.name: spec})

    raw_result = execute_with_retry(
        spec.func, max_attempts=spec.max_attempts, **arguments
    )

    try:
        return spec.output_model.model_validate(raw_result).model_dump()
    except ValidationError as exc:
        raise ToolCallError(
            "output_validation_error",
            "Tool output failed validation.",
            details=json.loads(exc.json()),
        ) from exc


# -------------------------------------------------------------------
# Run context
# -------------------------------------------------------------------


@dataclass
class AgentRun:
    """Everything one run_agent() call works with."""

    state: AgentState
    trace: AgentTrace
    client: Any
    store: RunStore
    tools: Mapping[str, ToolSpec]
    verbose: bool = False
    intent: str | None = None

    # Records every model call made through `client`.
    meter: UsageMeter = field(default_factory=UsageMeter)

    # Optional progress listener, e.g. the streaming API. Receives every
    # trace event as it happens.
    on_event: Callable[[str, dict[str, Any]], None] | None = None

    # Executions (including failures) per tool name and per tool category.
    counts: Counter[str] = field(default_factory=Counter)
    category_counts: Counter[str] = field(default_factory=Counter)
    seen_calls: set[tuple[str, str]] = field(default_factory=set)

    def event(self, event_type: str, **data: Any) -> None:
        add_event(self.trace, event_type, **data)

        if self.on_event is not None:
            try:
                self.on_event(event_type, data)
            except Exception:
                # A broken listener (say, a closed browser) must not stop
                # the run; the trace still records everything.
                logger.warning("Progress listener failed", exc_info=True)

    def log(self, *values: Any) -> None:
        if self.verbose:
            print(*values)

    def checkpoint(self, checkpoint_id: str) -> None:
        checkpoint = create_checkpoint(
            run_id=self.trace.run_id, checkpoint_id=checkpoint_id, state=self.state
        )

        path = self.store.save_checkpoint(checkpoint)

        self.event(
            "checkpoint_saved",
            checkpoint_id=checkpoint_id,
            path=str(path) if path else None,
            step=self.state.step_count,
        )

    def record_error(self, error_info: dict[str, Any], *, history: bool) -> None:
        self.state.errors.append(error_info)

        if history:
            self.state.tool_history.append(error_info)

    def stop(self, stop_reason: str, **guard_data: Any) -> None:
        """End the run because a controller guard fired."""

        self.state.stop_reason = stop_reason

        self.event("guard_triggered", **guard_data, step=self.state.step_count)


# -------------------------------------------------------------------
# Pipeline stages
# -------------------------------------------------------------------


def run_agent(
    question: str,
    verbose: bool = False,
    *,
    client: Any = None,
    store: RunStore | None = None,
    tools: Mapping[str, ToolSpec] | None = None,
    history: list[dict[str, str]] | None = None,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> AgentResult:
    """
    Run the Agentic BI application for one user question.

    `client`, `store` and `tools` default to the shared OpenAI client,
    on-disk run storage and the tool registry; tests pass fakes.

    `history` holds earlier turns ({"role", "content"}); a follow-up such
    as "and for JFK?" is first rewritten into a standalone question.
    `on_event` receives progress events while the run is in flight.
    """

    meter = UsageMeter()

    run = AgentRun(
        state=AgentState(goal=question),
        trace=create_trace(question=question),
        client=MeteredClient(
            client if client is not None else get_openai_client(), meter
        ),
        store=store if store is not None else default_run_store(),
        tools=tools if tools is not None else TOOL_REGISTRY,
        verbose=verbose,
        on_event=on_event,
        meter=meter,
    )

    run.event("agent_started")

    if history:
        run.meter.stage = "follow-up"
        standalone = condense_question(question, history, client=run.client)

        if standalone != question:
            run.state.goal = standalone
            run.event("question_rewritten", original=question, standalone=standalone)

    early_result = interaction_gate(run)

    if early_result is not None:
        return early_result

    choose_skill(run)

    final_answer = run_tool_loop(run)

    return finish_run(run, final_answer)


def interaction_gate(run: AgentRun) -> AgentResult | None:
    """
    Classify the question and finish runs that need no tool loop.

    Returns the result for greetings, app questions, out-of-scope
    requests and current-information questions; None otherwise.
    """

    run.meter.stage = "routing"

    interaction = classify_interaction(run.state.goal, client=run.client)

    run.intent = interaction.intent

    run.event(
        "interaction_classified", intent=interaction.intent, reason=interaction.reason
    )

    run.log("Interaction intent:", interaction.intent)

    if interaction.intent == "current_airline_info":
        run.meter.stage = "web answer"

        current_info = answer_current_delta_question(run.state.goal, client=run.client)

        run.state.stop_reason = "current_airline_info"
        run.counts[WEB_SEARCH_TOOL] += 1
        run.category_counts["web"] += 1

        run.event(
            "current_airline_info_retrieved",
            source_type=current_info.get("source_type"),
            provider=current_info.get("provider"),
            source_count=len(current_info.get("sources", [])),
        )

        return finish_run(
            run, current_info["answer"], sources=list(current_info.get("sources", []))
        )

    interaction_response = build_interaction_response(
        intent=interaction.intent, question=run.state.goal
    )

    if interaction_response is not None:
        run.state.stop_reason = "interaction_response"

        run.event("interaction_handled", intent=interaction.intent)

        return finish_run(run, interaction_response)

    return None


def choose_skill(run: AgentRun) -> None:
    """
    Pick the skill for the tool loop.

    The interaction router already decided data vs. documents; the
    keyword router is only a fallback for unmapped intents.
    """

    run.state.selected_skill = INTENT_TO_SKILL.get(run.intent)

    skill_source = "interaction_router"

    if run.state.selected_skill is None:
        run.state.selected_skill = select_skill(run.state.goal)

        skill_source = "keyword_router"

    run.event("skill_selected", skill=run.state.selected_skill, source=skill_source)

    run.log("Selected skill:", run.state.selected_skill)


def run_tool_loop(run: AgentRun) -> str:
    """
    Alternate model calls and tool calls until the model answers or a
    budget or guard stops the run. Returns the final answer text.
    """

    state = run.state

    run.meter.stage = "agent"

    skill_content = load_skill(state.selected_skill) if state.selected_skill else ""

    instructions = build_agent_instructions(
        selected_skill=state.selected_skill, skill_content=skill_content
    )

    # Web search is offered only to knowledge-analysis.
    specs = get_tool_specs_for_skill(state.selected_skill, run.tools)
    tools = [spec.openai_tool() for spec in specs]
    allowed_tool_names = {spec.name for spec in specs}

    response = run.client.responses.create(
        model=openai_model(), input=state.goal, instructions=instructions, tools=tools
    )

    while state.step_count < MAX_STEPS:
        state.step_count += 1

        run.log(f"\n--- Agent step {state.step_count} ---")

        function_calls = [
            item for item in response.output if item.type == "function_call"
        ]

        if not function_calls:
            state.stop_reason = "final_answer"
            break

        # Web fallback requires private evidence from an earlier step.
        knowledge_searches_before_step = run.counts[KNOWLEDGE_SEARCH_TOOL]

        tool_outputs = []

        for item in function_calls:
            output = handle_tool_call(
                run, item, allowed_tool_names, knowledge_searches_before_step
            )

            if output is None:
                break

            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": output,
                }
            )

        if state.stop_reason is not None:
            break

        if must_answer_now(run):
            response = run.client.responses.create(
                model=openai_model(),
                previous_response_id=response.id,
                input=tool_outputs,
                instructions=build_final_answer_instructions(instructions),
            )

            state.stop_reason = "final_answer"
            break

        response = run.client.responses.create(
            model=openai_model(),
            previous_response_id=response.id,
            input=tool_outputs,
            instructions=instructions,
            tools=tools,
        )

    if state.stop_reason is None:
        state.stop_reason = "max_steps_reached"

    return response.output_text if state.stop_reason == "final_answer" else ""


def must_answer_now(run: AgentRun) -> bool:
    """True when a tool that ends this skill's research is out of budget."""

    for tool_name in FINAL_ANSWER_TRIGGERS.get(run.state.selected_skill, ()):
        spec = run.tools.get(tool_name)

        if spec is None or spec.max_calls_per_run is None:
            continue

        if run.counts[tool_name] >= spec.max_calls_per_run:
            return True

    return False


def handle_tool_call(
    run: AgentRun,
    item: Any,
    allowed_tool_names: set[str],
    knowledge_searches_before_step: int,
) -> str | None:
    """
    Apply the controller guards to one model tool call and run it.

    Returns the tool output for the model, or None when a guard stopped
    the run (state.stop_reason is then set).
    """

    state = run.state

    if state.tool_call_count >= MAX_TOOL_CALLS:
        run.stop("tool_call_budget_exceeded", guard="tool_call_budget")
        return None

    spec = run.tools.get(item.name)

    if spec is None or item.name not in allowed_tool_names:
        run.record_error(
            {
                "tool": item.name,
                "error_type": "unknown_tool",
                "error": "Unknown tool requested",
            },
            history=False,
        )
        run.stop("blocked_unknown_tool", guard="unknown_tool", tool=item.name)
        return None

    try:
        arguments = parse_arguments(spec, item.arguments)
    except ToolCallError as exc:
        run.record_error(
            {
                "tool": item.name,
                "error_type": exc.error_type,
                "error": exc.error,
                "details": exc.details,
            },
            history=True,
        )
        run.event(
            "tool_validation_failed",
            tool=item.name,
            stage=(
                "argument_parsing"
                if exc.error_type == "argument_parse_error"
                else "input_validation"
            ),
            step=state.step_count,
            error=exc.error,
            details=exc.details,
        )
        run.log("Input validation failed:", item.name)
        return exc.model_output()

    call_signature = (item.name, json.dumps(arguments, sort_keys=True))

    if call_signature in run.seen_calls:
        run.record_error(
            {
                "tool": item.name,
                "arguments": arguments,
                "error_type": "repeated_tool_call",
                "error": "Repeated identical tool call",
            },
            history=False,
        )
        run.stop(
            "repeated_tool_call",
            guard="repeated_tool_call",
            tool=item.name,
            arguments=arguments,
        )
        return None

    if item.name == WEB_SEARCH_TOOL and knowledge_searches_before_step == 0:
        run.record_error(
            {
                "tool": item.name,
                "arguments": arguments,
                "error_type": "web_before_private_search",
                "error": (
                    "Official web search is only allowed after "
                    "private knowledge has been searched."
                ),
            },
            history=True,
        )
        run.event(
            "guard_triggered",
            guard="web_before_private_search",
            tool=item.name,
            step=state.step_count,
        )
        return ToolCallError(
            "web_before_private_search",
            "Search the private knowledge base first. Use official web "
            "search only if that evidence is insufficient.",
        ).model_output()

    if (
        spec.max_calls_per_run is not None
        and run.counts[spec.name] >= spec.max_calls_per_run
    ):
        label = BUDGET_LABELS.get(spec.name, spec.name)
        run.stop(f"{label}_budget_exceeded", guard=f"{label}_budget", tool=item.name)
        return None

    run.seen_calls.add(call_signature)

    state.tool_call_count += 1
    run.counts[spec.name] += 1
    run.category_counts[spec.category] += 1

    run.log("Tool selected:", item.name)
    run.log("Validated arguments:", arguments)

    return run_tool(run, spec, arguments)


def run_tool(run: AgentRun, spec: ToolSpec, arguments: dict[str, Any]) -> str:
    """Execute a tool that passed every guard and record the outcome."""

    state = run.state

    timer = ExecutionTimer()
    timer.start()

    run.event(
        "tool_started", tool=spec.name, arguments=arguments, step=state.step_count
    )

    try:
        result = execute_tool(spec, arguments)

    except ToolCallError as exc:
        run.record_error(
            {
                "tool": spec.name,
                "arguments": arguments,
                "error_type": exc.error_type,
                "details": exc.details,
            },
            history=True,
        )
        run.event(
            "tool_completed",
            tool=spec.name,
            step=state.step_count,
            duration_seconds=timer.stop(),
            status="error",
            error_type=exc.error_type,
        )
        run.log("Output validation failed:", spec.name)
        return exc.model_output()

    except Exception as exc:
        run.record_error(
            {
                "tool": spec.name,
                "arguments": arguments,
                "error_type": "tool_execution_error",
                "error": str(exc),
            },
            history=True,
        )
        run.event(
            "tool_completed",
            tool=spec.name,
            step=state.step_count,
            duration_seconds=timer.stop(),
            status="error",
            error_type="tool_execution_error",
            error=str(exc),
        )
        return ToolCallError("tool_execution_error", str(exc)).model_output()

    run.event(
        "tool_completed",
        tool=spec.name,
        step=state.step_count,
        duration_seconds=timer.stop(),
        status="success",
    )

    observation = {"tool": spec.name, "arguments": arguments, "result": result}

    state.observations.append(observation)
    state.tool_history.append(observation)

    run.checkpoint(f"step_{state.step_count}_tool_{state.tool_call_count}")

    run.log("Results returned:", len(result.get("results", [])))

    return json.dumps(result, ensure_ascii=False, default=str)


def finish_run(
    run: AgentRun, final_answer: str, *, sources: list[dict[str, Any]] | None = None
) -> AgentResult:
    """Save the final checkpoint and trace, and build the result."""

    state = run.state

    run.checkpoint("final")

    finish_trace(run.trace, stop_reason=state.stop_reason)

    tool_seconds = sum(
        event.data.get("duration_seconds") or 0.0
        for event in run.trace.events
        if event.event_type == "tool_completed"
    )

    usage = run.meter.summary(
        tool_seconds=tool_seconds, total_seconds=run.trace.duration_seconds
    )

    run.trace.usage = usage

    run.event(
        "agent_finished",
        stop_reason=state.stop_reason,
        step_count=state.step_count,
        tool_call_count=state.tool_call_count,
        error_count=len(state.errors),
        total_tokens=usage["total_tokens"],
        estimated_cost_usd=usage["estimated_cost_usd"],
    )

    trace_path = run.store.save_trace(run.trace)

    if trace_path is not None:
        run.log("Trace saved:", trace_path)

    if sources is None:
        sources = collect_sources(state.selected_skill, state.observations)

    return AgentResult(
        goal=state.goal,
        selected_skill=state.selected_skill,
        final_answer=final_answer,
        stop_reason=state.stop_reason,
        step_count=state.step_count,
        tool_call_count=state.tool_call_count,
        knowledge_search_count=run.category_counts["knowledge"],
        data_analysis_count=run.category_counts["data"],
        web_search_count=run.category_counts["web"],
        sources=sources,
        tool_history=list(state.tool_history),
        observations=list(state.observations),
        errors=list(state.errors),
        trace=run.trace,
        usage=usage,
    )


# -------------------------------------------------------------------
# Sources
# -------------------------------------------------------------------


def _results_of(observation: dict[str, Any]) -> list[dict[str, Any]]:
    result = observation.get("result")

    if not isinstance(result, dict):
        return []

    items = result.get("results")

    if not isinstance(items, list):
        return []

    return [item for item in items if isinstance(item, dict)]


def collect_sources(
    selected_skill: str | None, observations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Collect user-facing provenance from successful observations.

    Knowledge-analysis runs list each document page, then each official
    web page. Data-analysis runs list the dataset used for computation.
    """

    if selected_skill == "data-analysis":
        return [
            {
                "source_type": "dataset",
                "title": DATASET_TITLE,
                "page_number": None,
                "url": None,
            }
        ]

    if selected_skill != "knowledge-analysis":
        return []

    sources: list[dict[str, Any]] = []
    seen_pages: set[tuple[str, Any]] = set()
    seen_urls: set[str] = set()

    for observation in observations:
        if observation.get("tool") != KNOWLEDGE_SEARCH_TOOL:
            continue

        for evidence in _results_of(observation):
            source_name = evidence.get("source")
            page_number = evidence.get("page_number")
            key = (str(source_name), page_number)

            if not source_name or key in seen_pages:
                continue

            seen_pages.add(key)
            sources.append(
                {
                    "source_type": "private_document",
                    "title": str(source_name),
                    "page_number": page_number,
                    "url": None,
                }
            )

    for observation in observations:
        if observation.get("tool") != WEB_SEARCH_TOOL:
            continue

        for page in _results_of(observation):
            url = page.get("url")

            if not url or url in seen_urls:
                continue

            seen_urls.add(url)
            sources.append(
                {
                    "source_type": "live_official_web",
                    "title": str(page.get("title") or url),
                    "page_number": None,
                    "url": url,
                }
            )

    return sources
