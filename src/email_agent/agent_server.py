from datetime import datetime
from typing import Literal

from langchain_core.language_models.chat_models import (
    BaseChatModel,
)
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from email_agent.action.node import create_action_node
from email_agent.app_state import GraphState
from email_agent.calendar_service import book_calendar_event
from email_agent.llm import ModelPurpose, get_chat_model
from email_agent.runtime_context import (
    AgentContext,
    create_default_agent_context,
)
from email_agent.triage.node import create_triage_node


class CalendarState(TypedDict, total=False):
    event_draft: dict
    approval: Literal["approve", "reject"]
    event_id: str


def request_approval(state: GraphState) -> dict:
    """暂停执行，并把日程草稿交给真实用户确认。"""

    decision = interrupt(
        {
            "action": "book_calendar_event",
            "message": "是否将这个事项添加到日历？",
            "event": state["calendar_draft"],
        }
    )

    # decision 来自外部用户操作，而不是语言模型
    return {"approval": decision}


def route_after_approval(
    state: CalendarState,
) -> Literal["book", "end"]:
    if state["approval"] == "approve":
        return "book"

    return "end"


def book_event(state: GraphState) -> dict:
    draft = state.get("calendar_draft")

    if not draft:
        raise ValueError("缺少日历草稿")

    if draft.get("missing_fields"):
        raise ValueError(f"日历信息不完整：{draft['missing_fields']}")

    start_time = draft.get("start_time")
    end_time = draft.get("end_time")

    if not start_time or not end_time:
        raise ValueError("缺少开始时间或结束时间")

    event_id = book_calendar_event(
        title=draft["title"],
        start=datetime.fromisoformat(start_time),
        end=datetime.fromisoformat(end_time),
        location=draft.get("location") or "",
        notes=draft.get("notes") or "",
        calendar_name=draft.get("calendar_name") or "",
    )

    return {"event_id": event_id}


def route_after_triage(
    state: GraphState,
) -> Literal["action", "end"]:
    needs_reply = state.get("classification_decision") == "respond"

    needs_calendar_processing = state.get("calendar_action") != "none"

    if needs_reply or needs_calendar_processing:
        return "action"

    return "end"


def route_after_action(
    state: GraphState,
) -> Literal["approval", "end"]:
    draft = state.get("calendar_draft")

    if not draft:
        return "end"

    if state.get("calendar_available") is False:
        return "end"

    if draft.get("missing_fields"):
        return "end"

    if not draft.get("start_time"):
        return "end"

    if not draft.get("end_time"):
        return "end"

    return "approval"


def create_graph(
    triage_model: BaseChatModel | None = None,
    action_model: BaseChatModel | None = None,
    context: AgentContext | None = None,
    *,
    checkpointer: BaseCheckpointSaver,
):
    triage_llm = (
        triage_model
        if triage_model is not None
        else get_chat_model(ModelPurpose.TRIAGE)
    )

    action_llm = action_model or triage_llm

    if context is None:
        context = create_default_agent_context()

    builder = StateGraph(GraphState)

    builder.add_node(
        "triage_router",
        create_triage_node(triage_llm),
    )
    builder.add_node(
        "action_agent",
        create_action_node(action_llm, context),
    )
    builder.add_node(
        "request_approval",
        request_approval,
    )
    builder.add_node(
        "book_event",
        book_event,
    )

    builder.add_edge(START, "triage_router")

    builder.add_conditional_edges(
        "triage_router",
        route_after_triage,
        {
            "action": "action_agent",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "action_agent",
        route_after_action,
        {
            "approval": "request_approval",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "request_approval",
        route_after_approval,
        {
            "book": "book_event",
            "end": END,
        },
    )

    builder.add_edge("book_event", END)

    return builder.compile(
        checkpointer=checkpointer,
    )
