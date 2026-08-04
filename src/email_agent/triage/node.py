from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.language_models.chat_models import (
    BaseChatModel,
)
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from email_agent.app_state import GraphState
from email_agent.prompts import TRIAGE_SYSTEM_PROMPT
from email_agent.triage.schemas import TriageResult


def create_triage_node(
    model: BaseChatModel,
):
    """创建带结构化输出的邮件分类节点。"""

    structured_model = model.with_structured_output(TriageResult)

    def triage_node(state: GraphState) -> dict:
        email = state["email_input"]

        timezone = ZoneInfo("Asia/Shanghai")
        current_datetime = datetime.now(timezone).isoformat()

        email_prompt = f"""
<context>
Current datetime: {current_datetime}
User timezone: Asia/Shanghai
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

        result = structured_model.invoke(
            [
                SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
                HumanMessage(content=email_prompt),
            ],
            config={
                "tags": ["email-triage"],
                "metadata": {
                    "prompt_version": "triage-v1",
                    "model_purpose": "triage",
                },
            },
        )

        return {
            "classification_decision": (result.classification),
            "classification_reason": result.reason,
            "calendar_action": result.calendar_action,
            "calendar_draft": (
                result.calendar_draft.model_dump() if result.calendar_draft else None
            ),
        }

    return triage_node
