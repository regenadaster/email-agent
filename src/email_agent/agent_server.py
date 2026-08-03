from typing import Annotated, Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict

model = init_chat_model(
    "openai:gpt-5.5",
    temperature=0.5,
    timeout=300,
    max_tokens=25000,
)

from pydantic import BaseModel, Field

triage_system_prompt = """
You are an email triage assistant.

Classify each email into one of:
- ignore
- notify
- respond

Rules:

Emails that are not worth responding to:
- Marketing newsletters and promotional emails
- Spam or suspicious emails
- CC'd FYI threads with no direct questions

Emails that require notification:
- Important status updates
- Receipts, alerts, or confirmations requiring awareness
- Messages relevant to ongoing work but not requiring a reply

Emails that require a response:
- Direct questions
- Requests for action
- Scheduling requests
- Messages explicitly asking the user to reply
"""


class TriageResult(BaseModel):
    """邮件分类结果。"""

    classification: Literal[
        "ignore",
        "notify",
        "respond",
    ] = Field(description="邮件处理方式：忽略、通知用户或回复邮件")

    reason: str = Field(description="简短说明分类原因，不超过50个字")

    confidence: float = Field(ge=0, le=1, description="分类置信度，范围为0到1")


class GraphState(TypedDict):
    email_input: dict
    classification_decision: Literal["ignore", "respond", "notify"]
    messages: Annotated[list[AnyMessage], add_messages]
    loaded_memory: str
    remaining_steps: int


def triage_router(state: GraphState) -> dict:
    """根据处理后的输入生成结果。"""
    triage_model = model.with_structured_output(TriageResult)
    email = state["email_input"]

    email_text = f"""
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
        SystemMessage(content=triage_system_prompt),
        HumanMessage(content=email_text),
    ]

    result = triage_model.invoke(prompt)
    return {
        "classification_decision": result.classification,
        "classification_reason": result.reason,
    }


def create_graph():
    builder = StateGraph(GraphState)

    # 注册节点
    builder.add_node("triage_router", triage_router)

    # 添加边
    builder.add_edge(START, "triage_router")
    builder.add_edge("triage_router", END)

    # 4. 编译图
    return builder.compile()


graph = create_graph()
