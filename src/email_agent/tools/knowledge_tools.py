from langchain.tools import ToolRuntime, tool

from email_agent.runtime_context import AgentContext


@tool
def search_knowledge_base(
    query: str,
    limit: int,
    runtime: ToolRuntime[AgentContext],
) -> dict:
    """搜索内部知识库，用于回答产品、制度、流程和项目相关问题。"""
    knowledge = runtime.context.knowledge

    if knowledge is None:
        return {
            "available": False,
            "results": [],
            "error": "知识库服务未配置",
        }

    hits = knowledge.search(query=query, limit=min(limit, 10))

    return {
        "available": True,
        "results": [hit.model_dump(mode="json") for hit in hits],
    }
