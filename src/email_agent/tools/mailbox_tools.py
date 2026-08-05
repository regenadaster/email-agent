# tools/mailbox_tools.py

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field

from email_agent.runtime_context import AgentContext


class SearchRelatedEmailsInput(BaseModel):
    query: str = Field(description="邮件搜索条件，例如发件人、主题关键词或项目名称")
    limit: int = Field(
        ge=1,
        le=10,
        description="最大返回数量，必须为 1 到 10",
    )


@tool(
    "search_related_emails",
    args_schema=SearchRelatedEmailsInput,
)
def search_related_emails(
    query: str,
    limit: int,
    runtime: ToolRuntime[AgentContext],
) -> dict:
    """搜索与当前邮件有关的历史邮件。

    当需要确认历史沟通、已有承诺、之前的回复或上下文时调用。
    不得用本工具读取与当前任务无关的私人邮件。
    """
    mailbox = runtime.context.mailbox
    if mailbox is None:
        return {
            "available": False,
            "results": [],
            "error": "邮箱搜索服务未配置",
        }

    results = mailbox.search(query=query, limit=limit)

    return {
        "available": True,
        "results": [result.model_dump(mode="json") for result in results],
    }
