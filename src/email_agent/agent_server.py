from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from email_agent.calendar_service import book_calendar_event
from email_agent.prompts import TRIAGE_SYSTEM_PROMPT

model = init_chat_model(
    "openai:gpt-5.5",
    temperature=0.5,
    timeout=300,
    max_tokens=25000,
)

from pydantic import BaseModel, Field


class CalendarDraft(BaseModel):
    """待用户确认的日历草稿。"""

    title: str = Field(description="日历事件标题")

    start_time: str | None = Field(
        default=None,
        description="ISO 8601 开始时间，必须包含时区",
    )

    end_time: str | None = Field(
        default=None,
        description="ISO 8601 结束时间，必须包含时区",
    )

    timezone: str | None = Field(
        default=None,
        description="IANA 时区，例如 Asia/Shanghai",
    )

    location: str | None = Field(
        default=None,
        description="会议地点或线上会议地址",
    )

    notes: str | None = Field(
        default=None,
        description="事件说明",
    )

    missing_fields: list[str] = Field(
        default_factory=list,
        description="仍需用户补充或确认的信息",
    )


class TriageResult(BaseModel):
    """邮件分类结果。"""

    classification: Literal[
        "ignore",
        "notify",
        "respond",
    ] = Field(description="邮件处理方式：忽略、通知用户或回复邮件")

    reason: str = Field(description="简短说明分类原因，不超过50个字")

    confidence: float = Field(ge=0, le=1, description="分类置信度，范围为0到1")
    calendar_action: Literal[
        "none",
        "needs_clarification",
        "propose",
    ] = Field(description="日历处理方式")

    calendar_draft: CalendarDraft | None = Field(
        default=None,
        description="日历事件草稿；没有日历事项时为 null",
    )


class GraphState(TypedDict):
    email_input: dict
    classification_decision: Literal[
        "ignore",
        "respond",
        "notify",
    ]
    classification_reason: str
    calendar_action: Literal[
        "none",
        "needs_clarification",
        "propose",
    ]
    calendar_draft: dict | None
    approval: Literal["approve", "reject"]
    event_id: str
    calendar_error: str


def triage_router(state: GraphState) -> dict:
    """根据处理后的输入生成结果。"""
    triage_model = model.with_structured_output(TriageResult)
    email = state["email_input"]
    timezone = ZoneInfo("Asia/Shanghai")
    current_datetime = datetime.now(timezone).isoformat()

    email_prompt = f"""
<context>
Current datetime: {current_datetime}
User timezone: Asia/Beijing
</context>
请判断下面这封邮件应该如何处理。

收件人：
{email["to"]}

发件人：
{email["author"]}

主题：
{email["subject"]}

邮件正文：
{email["email_thread"]}
"""

    prompt = [
        SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
        HumanMessage(content=email_prompt),
    ]

    result = triage_model.invoke(prompt)
    return {
        "classification_decision": result.classification,
        "classification_reason": result.reason,
        "calendar_action": result.calendar_action,
        "calendar_draft": (
            result.calendar_draft.model_dump() if result.calendar_draft else None
        ),
    }


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
) -> Literal["approval", "end"]:
    draft = state.get("calendar_draft")

    if (
        state.get("calendar_action") == "propose"
        and draft
        and not draft.get("missing_fields")
        and draft.get("start_time")
        and draft.get("end_time")
    ):
        return "approval"

    return "end"


def create_graph():
    builder = StateGraph(GraphState)

    # 注册节点
    builder.add_node("triage_router", triage_router)
    builder.add_node("request_approval", request_approval)
    builder.add_node("book_event", book_event)

    # 添加边
    builder.add_edge(START, "triage_router")

    builder.add_conditional_edges(
        "triage_router",
        route_after_triage,
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
    # 4. 编译图
    return builder.compile(
        checkpointer=InMemorySaver(),
    )


graph = create_graph()
