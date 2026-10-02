import json
import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from agentic_bi.core.checkpoint import (
    create_checkpoint,
    save_checkpoint,
)
from agentic_bi.core.observability import (
    AgentTrace,
    ExecutionTimer,
    add_event,
    create_trace,
    finish_trace,
    save_trace,
)
from agentic_bi.core.prompts import (
    build_agent_instructions,
    build_final_answer_instructions,
)
from agentic_bi.core.reliability import execute_with_retry
from agentic_bi.core.interaction import classify_interaction
from agentic_bi.core.interaction_response import build_interaction_response
from agentic_bi.core.state import AgentState
from agentic_bi.skills.loader import load_skill
from agentic_bi.skills.router import select_skill
from agentic_bi.tools.delta_current_info import (
    answer_current_delta_question,
)
from agentic_bi.tools.registry import (
    FUNCTIONS,
    INPUT_SCHEMAS,
    OUTPUT_SCHEMAS,
    TOOL_POLICIES,
    get_tools_for_skill,
)


load_dotenv()


MAX_STEPS = 4
MAX_TOOL_CALLS = 4
MAX_KNOWLEDGE_SEARCHES = 2
MAX_DATA_ANALYSIS_CALLS = 1
MAX_WEB_SEARCHES = 1

WEB_SEARCH_TOOL = "search_official_web"

INTENT_TO_SKILL = {
    "airline_knowledge": "knowledge-analysis",
    "airline_data": "data-analysis",
}


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

    sources: list[dict[str, Any]] = field(
        default_factory=list
    )

    tool_history: list[dict[str, Any]] = field(
        default_factory=list
    )

    observations: list[dict[str, Any]] = field(
        default_factory=list
    )

    errors: list[dict[str, Any]] = field(
        default_factory=list
    )

    trace: AgentTrace | None = None


def _collect_sources(
    selected_skill: str | None,
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Collect user-facing provenance from successful observations.

    Knowledge-analysis runs expose retrieved document/page
    references. Data-analysis runs expose the dataset used
    for deterministic computation.
    """

    sources: list[dict[str, Any]] = []

    if selected_skill == "knowledge-analysis":
        seen: set[tuple[str, Any]] = set()

        for observation in observations:
            if (
                observation.get("tool")
                != "search_private_knowledge"
            ):
                continue

            result = observation.get(
                "result",
                {},
            )

            if not isinstance(
                result,
                dict,
            ):
                continue

            evidence_items = result.get(
                "results",
                [],
            )

            if not isinstance(
                evidence_items,
                list,
            ):
                continue

            for evidence in evidence_items:
                if not isinstance(
                    evidence,
                    dict,
                ):
                    continue

                source_name = evidence.get(
                    "source"
                )

                page_number = evidence.get(
                    "page_number"
                )

                if not source_name:
                    continue

                key = (
                    str(source_name),
                    page_number,
                )

                if key in seen:
                    continue

                seen.add(
                    key
                )

                sources.append(
                    {
                        "source_type":
                            "private_document",
                        "title":
                            str(source_name),
                        "page_number":
                            page_number,
                        "url":
                            None,
                    }
                )

    if selected_skill == "knowledge-analysis":
        seen_urls: set[str] = set()

        for observation in observations:
            if observation.get("tool") != WEB_SEARCH_TOOL:
                continue

            result = observation.get("result", {})

            if not isinstance(result, dict):
                continue

            for page in result.get("results", []):
                if not isinstance(page, dict):
                    continue

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

    elif selected_skill == "data-analysis":
        sources.append(
            {
                "source_type":
                    "dataset",
                "title": (
                    "Delta-marketed domestic "
                    "flight data — July 2026"
                ),
                "page_number":
                    None,
                "url":
                    None,
            }
        )

    return sources


def run_agent(
    question: str,
    verbose: bool = False,
) -> AgentResult:
    """
    Run the Agentic BI application for one user question.

    Returns structured execution information so the same
    agent can be reused by demos, evaluation, tests, APIs,
    and observability tooling.
    """

    client = OpenAI()

    # ---------------------------------------------------------------
    # Observability trace
    # ---------------------------------------------------------------

    trace = create_trace(
        question=question
    )

    add_event(
        trace,
        "agent_started",
    )

    # ---------------------------------------------------------------
    # Agent state
    # ---------------------------------------------------------------

    state = AgentState(
        goal=question
    )

    # ---------------------------------------------------------------
    # Interaction routing
    # ---------------------------------------------------------------

    interaction = classify_interaction(
        state.goal,
        client=client,
    )

    add_event(
        trace,
        "interaction_classified",
        intent=interaction.intent,
        reason=interaction.reason,
    )

    if verbose:
        print(
            "Interaction intent:",
            interaction.intent,
        )

    interaction_response = build_interaction_response(
        intent=interaction.intent,
        question=state.goal,
    )

    # ---------------------------------------------------------------
    # Current official-web information
    # ---------------------------------------------------------------

    if interaction.intent == "current_airline_info":
        current_info = answer_current_delta_question(
            state.goal
        )

        state.stop_reason = "current_airline_info"

        add_event(
            trace,
            "current_airline_info_retrieved",
            source_type=current_info.get(
                "source_type"
            ),
            provider=current_info.get(
                "provider"
            ),
            source_count=len(
                current_info.get(
                    "sources",
                    [],
                )
            ),
        )

        final_checkpoint = create_checkpoint(
            run_id=trace.run_id,
            checkpoint_id="final",
            state=state,
        )

        final_checkpoint_path = save_checkpoint(
            final_checkpoint
        )

        add_event(
            trace,
            "checkpoint_saved",
            checkpoint_id="final",
            path=str(final_checkpoint_path),
            step=state.step_count,
        )

        add_event(
            trace,
            "agent_finished",
            stop_reason=state.stop_reason,
            step_count=state.step_count,
            tool_call_count=state.tool_call_count,
            error_count=len(state.errors),
        )

        finish_trace(
            trace,
            stop_reason=state.stop_reason,
        )

        save_trace(
            trace
        )

        return AgentResult(
            goal=state.goal,
            selected_skill=None,
            final_answer=current_info["answer"],
            stop_reason=state.stop_reason,
            step_count=state.step_count,
            tool_call_count=state.tool_call_count,
            knowledge_search_count=0,
            data_analysis_count=0,
            web_search_count=1,
            sources=list(
                current_info.get(
                    "sources",
                    [],
                )
            ),
            tool_history=list(
                state.tool_history
            ),
            observations=list(
                state.observations
            ),
            errors=list(
                state.errors
            ),
            trace=trace,
        )

    # ---------------------------------------------------------------
    # Bounded interaction responses
    # ---------------------------------------------------------------

    if interaction_response is not None:
        state.stop_reason = "interaction_response"

        add_event(
            trace,
            "interaction_handled",
            intent=interaction.intent,
        )

        final_checkpoint = create_checkpoint(
            run_id=trace.run_id,
            checkpoint_id="final",
            state=state,
        )

        final_checkpoint_path = save_checkpoint(
            final_checkpoint
        )

        add_event(
            trace,
            "checkpoint_saved",
            checkpoint_id="final",
            path=str(final_checkpoint_path),
            step=state.step_count,
        )

        add_event(
            trace,
            "agent_finished",
            stop_reason=state.stop_reason,
            step_count=state.step_count,
            tool_call_count=state.tool_call_count,
            error_count=len(state.errors),
        )

        finish_trace(
            trace,
            stop_reason=state.stop_reason,
        )

        save_trace(
            trace
        )

        return AgentResult(
            goal=state.goal,
            selected_skill=None,
            final_answer=interaction_response,
            stop_reason=state.stop_reason,
            step_count=state.step_count,
            tool_call_count=state.tool_call_count,
            knowledge_search_count=0,
            data_analysis_count=0,
            tool_history=list(
                state.tool_history
            ),
            observations=list(
                state.observations
            ),
            errors=list(
                state.errors
            ),
            trace=trace,
        )

    # ---------------------------------------------------------------
    # Skill selection
    # ---------------------------------------------------------------

    # The interaction router already decided data vs. documents.
    # The keyword router is only a fallback for unmapped intents.
    state.selected_skill = INTENT_TO_SKILL.get(
        interaction.intent
    )

    skill_source = "interaction_router"

    if state.selected_skill is None:
        state.selected_skill = select_skill(
            state.goal
        )

        skill_source = "keyword_router"

    add_event(
        trace,
        "skill_selected",
        skill=state.selected_skill,
        source=skill_source,
    )

    skill_content = ""

    if state.selected_skill is not None:
        skill_content = load_skill(
            state.selected_skill
        )

    if verbose:
        print(
            "Selected skill:",
            state.selected_skill,
        )

    # ---------------------------------------------------------------
    # Instructions
    # ---------------------------------------------------------------

    instructions = build_agent_instructions(
        selected_skill=state.selected_skill,
        skill_content=skill_content,
    )

    # ---------------------------------------------------------------
    # Runtime guards
    # ---------------------------------------------------------------

    seen_tool_calls = set()

    knowledge_search_count = 0
    data_analysis_count = 0
    web_search_count = 0

    # Web search is offered only to knowledge-analysis.
    tools = get_tools_for_skill(
        state.selected_skill
    )

    allowed_tool_names = {
        tool["name"]
        for tool in tools
    }

    # ---------------------------------------------------------------
    # Initial model decision
    # ---------------------------------------------------------------

    response = client.responses.create(
        model=os.environ["OPENAI_MODEL"],
        input=state.goal,
        instructions=instructions,
        tools=tools,
    )

    # ---------------------------------------------------------------
    # Bounded agent loop
    # ---------------------------------------------------------------

    while state.step_count < MAX_STEPS:

        state.step_count += 1

        if verbose:
            print(
                f"\n--- Agent step {state.step_count} ---"
            )

        function_calls = [
            item
            for item in response.output
            if item.type == "function_call"
        ]

        # -----------------------------------------------------------
        # Normal completion
        # -----------------------------------------------------------

        if not function_calls:
            state.stop_reason = "final_answer"
            break

        tool_outputs = []

        # Web fallback requires private evidence from an earlier step.
        knowledge_searches_before_step = (
            knowledge_search_count
        )

        # -----------------------------------------------------------
        # Process tool calls
        # -----------------------------------------------------------

        for item in function_calls:

            # -------------------------------------------------------
            # Global tool budget
            # -------------------------------------------------------

            if state.tool_call_count >= MAX_TOOL_CALLS:

                state.stop_reason = (
                    "tool_call_budget_exceeded"
                )

                add_event(
                    trace,
                    "guard_triggered",
                    guard="tool_call_budget",
                    step=state.step_count,
                )

                break

            # -------------------------------------------------------
            # Tool allowlist
            # -------------------------------------------------------

            if (
                item.name not in FUNCTIONS
                or item.name not in allowed_tool_names
            ):

                state.stop_reason = (
                    "blocked_unknown_tool"
                )

                error_info = {
                    "tool": item.name,
                    "error_type": "unknown_tool",
                    "error": "Unknown tool requested",
                }

                state.errors.append(
                    error_info
                )

                add_event(
                    trace,
                    "guard_triggered",
                    guard="unknown_tool",
                    tool=item.name,
                    step=state.step_count,
                )

                break

            # -------------------------------------------------------
            # Parse arguments
            # -------------------------------------------------------

            try:

                arguments = json.loads(
                    item.arguments
                )

            except json.JSONDecodeError as exc:

                error_info = {
                    "tool": item.name,
                    "error_type":
                        "argument_parse_error",
                    "error": str(exc),
                }

                state.errors.append(
                    error_info
                )

                state.tool_history.append(
                    error_info
                )

                add_event(
                    trace,
                    "tool_validation_failed",
                    tool=item.name,
                    stage="argument_parsing",
                    step=state.step_count,
                    error=str(exc),
                )

                tool_outputs.append(
                    {
                        "type":
                            "function_call_output",
                        "call_id":
                            item.call_id,
                        "output":
                            json.dumps(
                                {
                                    "status":
                                        "error",
                                    "error_type":
                                        "argument_parse_error",
                                    "message":
                                        "Tool arguments were not valid JSON.",
                                }
                            ),
                    }
                )

                continue

            # -------------------------------------------------------
            # Validate input
            # -------------------------------------------------------

            try:

                validated_input = (
                    INPUT_SCHEMAS[
                        item.name
                    ].model_validate(
                        arguments
                    )
                )

                arguments = (
                    validated_input.model_dump()
                )

            except ValidationError as exc:

                validation_details = json.loads(
                    exc.json()
                )

                error_info = {
                    "tool": item.name,
                    "arguments": arguments,
                    "error_type":
                        "input_validation_error",
                    "details":
                        validation_details,
                }

                state.errors.append(
                    error_info
                )

                state.tool_history.append(
                    error_info
                )

                add_event(
                    trace,
                    "tool_validation_failed",
                    tool=item.name,
                    stage="input_validation",
                    step=state.step_count,
                    details=validation_details,
                )

                if verbose:
                    print(
                        "Input validation failed:",
                        item.name,
                    )

                tool_outputs.append(
                    {
                        "type":
                            "function_call_output",
                        "call_id":
                            item.call_id,
                        "output":
                            json.dumps(
                                {
                                    "status":
                                        "error",
                                    "error_type":
                                        "input_validation_error",
                                    "message":
                                        "Tool arguments failed validation.",
                                    "details":
                                        validation_details,
                                }
                            ),
                    }
                )

                continue

            # -------------------------------------------------------
            # Duplicate-call guard
            # -------------------------------------------------------

            call_signature = (
                item.name,
                json.dumps(
                    arguments,
                    sort_keys=True,
                ),
            )

            if call_signature in seen_tool_calls:

                state.stop_reason = (
                    "repeated_tool_call"
                )

                error_info = {
                    "tool": item.name,
                    "arguments": arguments,
                    "error_type":
                        "repeated_tool_call",
                    "error":
                        "Repeated identical tool call",
                }

                state.errors.append(
                    error_info
                )

                add_event(
                    trace,
                    "guard_triggered",
                    guard="repeated_tool_call",
                    tool=item.name,
                    arguments=arguments,
                    step=state.step_count,
                )

                break

            # -------------------------------------------------------
            # Web fallback: private documents first
            # -------------------------------------------------------

            if (
                item.name == WEB_SEARCH_TOOL
                and knowledge_searches_before_step == 0
            ):

                error_info = {
                    "tool": item.name,
                    "arguments": arguments,
                    "error_type": "web_before_private_search",
                    "error": (
                        "Official web search is only allowed after "
                        "private knowledge has been searched."
                    ),
                }

                state.errors.append(
                    error_info
                )

                state.tool_history.append(
                    error_info
                )

                add_event(
                    trace,
                    "guard_triggered",
                    guard="web_before_private_search",
                    tool=item.name,
                    step=state.step_count,
                )

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": json.dumps(
                            {
                                "status": "error",
                                "error_type":
                                    "web_before_private_search",
                                "message": (
                                    "Search the private knowledge "
                                    "base first. Use official web "
                                    "search only if that evidence "
                                    "is insufficient."
                                ),
                            }
                        ),
                    }
                )

                continue

            # -------------------------------------------------------
            # Per-tool budgets
            # -------------------------------------------------------

            if (
                item.name == WEB_SEARCH_TOOL
                and web_search_count
                >= MAX_WEB_SEARCHES
            ):

                state.stop_reason = (
                    "web_search_budget_exceeded"
                )

                add_event(
                    trace,
                    "guard_triggered",
                    guard="web_search_budget",
                    tool=item.name,
                    step=state.step_count,
                )

                break

            if (
                item.name
                == "search_private_knowledge"
                and knowledge_search_count
                >= MAX_KNOWLEDGE_SEARCHES
            ):

                state.stop_reason = (
                    "knowledge_search_budget_exceeded"
                )

                add_event(
                    trace,
                    "guard_triggered",
                    guard="knowledge_search_budget",
                    tool=item.name,
                    step=state.step_count,
                )

                break

            if (
                item.name
                == "analyze_top_origin_cancellation_rates"
                and data_analysis_count
                >= MAX_DATA_ANALYSIS_CALLS
            ):

                state.stop_reason = (
                    "data_analysis_budget_exceeded"
                )

                add_event(
                    trace,
                    "guard_triggered",
                    guard="data_analysis_budget",
                    tool=item.name,
                    step=state.step_count,
                )

                break

            seen_tool_calls.add(
                call_signature
            )

            # -------------------------------------------------------
            # Record execution attempt
            # -------------------------------------------------------

            state.tool_call_count += 1

            if (
                item.name
                == "search_private_knowledge"
            ):
                knowledge_search_count += 1

            elif (
                item.name
                == "analyze_top_origin_cancellation_rates"
            ):
                data_analysis_count += 1

            elif item.name == WEB_SEARCH_TOOL:
                web_search_count += 1

            if verbose:

                print(
                    "Tool selected:",
                    item.name,
                )

                print(
                    "Validated arguments:",
                    arguments,
                )

            # -------------------------------------------------------
            # Execute tool
            # -------------------------------------------------------

            tool_timer = ExecutionTimer()
            tool_timer.start()

            add_event(
                trace,
                "tool_started",
                tool=item.name,
                arguments=arguments,
                step=state.step_count,
            )

            try:

                policy = TOOL_POLICIES[
                    item.name
                ]

                raw_result = execute_with_retry(
                    FUNCTIONS[item.name],
                    max_attempts=policy[
                        "max_attempts"
                    ],
                    **arguments,
                )

                # ---------------------------------------------------
                # Validate output
                # ---------------------------------------------------

                try:

                    validated_output = (
                        OUTPUT_SCHEMAS[
                            item.name
                        ].model_validate(
                            raw_result
                        )
                    )

                    result = (
                        validated_output.model_dump()
                    )

                    if verbose:
                        print(
                            "Output validated:",
                            item.name,
                        )

                except ValidationError as exc:

                    tool_duration = (
                        tool_timer.stop()
                    )

                    validation_details = json.loads(
                        exc.json()
                    )

                    error_info = {
                        "tool": item.name,
                        "arguments": arguments,
                        "error_type":
                            "output_validation_error",
                        "details":
                            validation_details,
                    }

                    state.errors.append(
                        error_info
                    )

                    state.tool_history.append(
                        error_info
                    )

                    add_event(
                        trace,
                        "tool_completed",
                        tool=item.name,
                        step=state.step_count,
                        duration_seconds=
                            tool_duration,
                        status="error",
                        error_type=
                            "output_validation_error",
                    )

                    if verbose:
                        print(
                            "Output validation failed:",
                            item.name,
                        )

                    tool_outputs.append(
                        {
                            "type":
                                "function_call_output",
                            "call_id":
                                item.call_id,
                            "output":
                                json.dumps(
                                    {
                                        "status":
                                            "error",
                                        "error_type":
                                            "output_validation_error",
                                        "message":
                                            "Tool output failed validation.",
                                        "details":
                                            validation_details,
                                    }
                                ),
                        }
                    )

                    continue

                # ---------------------------------------------------
                # Successful observation
                # ---------------------------------------------------

                tool_duration = (
                    tool_timer.stop()
                )

                add_event(
                    trace,
                    "tool_completed",
                    tool=item.name,
                    step=state.step_count,
                    duration_seconds=
                        tool_duration,
                    status="success",
                )

                observation = {
                    "tool": item.name,
                    "arguments": arguments,
                    "result": result,
                }

                state.observations.append(
                    observation
                )

                state.tool_history.append(
                    observation
                )

                # ---------------------------------------------------
                # Persist step checkpoint
                # ---------------------------------------------------

                checkpoint = create_checkpoint(
                    run_id=trace.run_id,
                    checkpoint_id=(
                        f"step_{state.step_count}"
                        f"_tool_{state.tool_call_count}"
                    ),
                    state=state,
                )

                checkpoint_path = (
                    save_checkpoint(
                        checkpoint
                    )
                )

                add_event(
                    trace,
                    "checkpoint_saved",
                    checkpoint_id=
                        checkpoint.checkpoint_id,
                    path=str(
                        checkpoint_path
                    ),
                    step=state.step_count,
                )

                if verbose:

                    if (
                        item.name
                        == "search_private_knowledge"
                    ):

                        print(
                            "Evidence retrieved:",
                            len(
                                result["results"]
                            ),
                        )

                    elif (
                        item.name
                        == "analyze_top_origin_cancellation_rates"
                    ):

                        print(
                            "Rows returned:",
                            len(
                                result["results"]
                            ),
                        )

                output = json.dumps(
                    result,
                    ensure_ascii=False,
                    default=str,
                )

            # -------------------------------------------------------
            # Tool execution failure
            # -------------------------------------------------------

            except Exception as exc:

                tool_duration = (
                    tool_timer.stop()
                )

                error_info = {
                    "tool": item.name,
                    "arguments": arguments,
                    "error_type":
                        "tool_execution_error",
                    "error": str(exc),
                }

                state.errors.append(
                    error_info
                )

                state.tool_history.append(
                    error_info
                )

                add_event(
                    trace,
                    "tool_completed",
                    tool=item.name,
                    step=state.step_count,
                    duration_seconds=
                        tool_duration,
                    status="error",
                    error_type=
                        "tool_execution_error",
                    error=str(exc),
                )

                output = json.dumps(
                    {
                        "status": "error",
                        "error_type":
                            "tool_execution_error",
                        "message": str(exc),
                    }
                )

            # -------------------------------------------------------
            # Return observation to model
            # -------------------------------------------------------

            tool_outputs.append(
                {
                    "type":
                        "function_call_output",
                    "call_id":
                        item.call_id,
                    "output":
                        output,
                }
            )

        # -----------------------------------------------------------
        # Controller-level stop
        # -----------------------------------------------------------

        if state.stop_reason is not None:
            break

        # -----------------------------------------------------------
        # Determine whether to force final synthesis
        # -----------------------------------------------------------

        force_final_answer = (
            (
                state.selected_skill
                == "knowledge-analysis"
                and (
                    knowledge_search_count
                    >= MAX_KNOWLEDGE_SEARCHES
                    or web_search_count
                    >= MAX_WEB_SEARCHES
                )
            )
            or
            (
                state.selected_skill
                == "data-analysis"
                and data_analysis_count
                >= MAX_DATA_ANALYSIS_CALLS
            )
        )

        # -----------------------------------------------------------
        # Force final answer
        # -----------------------------------------------------------

        if force_final_answer:

            final_instructions = (
                build_final_answer_instructions(
                    instructions
                )
            )

            response = client.responses.create(
                model=os.environ[
                    "OPENAI_MODEL"
                ],
                previous_response_id=
                    response.id,
                input=tool_outputs,
                instructions=
                    final_instructions,
            )

            state.stop_reason = (
                "final_answer"
            )

            break

        # -----------------------------------------------------------
        # Continue agent reasoning
        # -----------------------------------------------------------

        response = client.responses.create(
            model=os.environ["OPENAI_MODEL"],
            previous_response_id=response.id,
            input=tool_outputs,
            instructions=instructions,
            tools=tools,
        )

    # ---------------------------------------------------------------
    # Termination
    # ---------------------------------------------------------------

    if state.stop_reason is None:
        state.stop_reason = (
            "max_steps_reached"
        )

    final_answer = ""

    if state.stop_reason == "final_answer":
        final_answer = response.output_text

    # ---------------------------------------------------------------
    # Persist final state checkpoint
    # ---------------------------------------------------------------

    final_checkpoint = create_checkpoint(
        run_id=trace.run_id,
        checkpoint_id="final",
        state=state,
    )

    final_checkpoint_path = (
        save_checkpoint(
            final_checkpoint
        )
    )

    add_event(
        trace,
        "checkpoint_saved",
        checkpoint_id="final",
        path=str(
            final_checkpoint_path
        ),
        step=state.step_count,
    )

    # ---------------------------------------------------------------
    # Finish observability trace
    # ---------------------------------------------------------------

    add_event(
        trace,
        "agent_finished",
        stop_reason=state.stop_reason,
        step_count=state.step_count,
        tool_call_count=state.tool_call_count,
        error_count=len(state.errors),
    )

    finish_trace(
        trace,
        stop_reason=state.stop_reason,
    )

    trace_path = save_trace(
        trace
    )

    if verbose:
        print(
            "Trace saved:",
            trace_path,
        )

    # ---------------------------------------------------------------
    # Structured result
    # ---------------------------------------------------------------

    sources = _collect_sources(
        selected_skill=state.selected_skill,
        observations=state.observations,
    )

    return AgentResult(
        goal=state.goal,
        selected_skill=state.selected_skill,
        final_answer=final_answer,
        stop_reason=state.stop_reason,
        step_count=state.step_count,
        tool_call_count=state.tool_call_count,
        knowledge_search_count=
            knowledge_search_count,
        data_analysis_count=
            data_analysis_count,
        web_search_count=web_search_count,
        sources=sources,
        tool_history=list(
            state.tool_history
        ),
        observations=list(
            state.observations
        ),
        errors=list(
            state.errors
        ),
        trace=trace,
    )