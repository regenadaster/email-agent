from enum import StrEnum
from functools import cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from email_agent.llm.settings import get_model_settings


class ModelPurpose(StrEnum):
    """模型用途。"""

    TRIAGE = "triage"


@cache
def get_chat_model(
    purpose: ModelPurpose,
) -> BaseChatModel:
    settings = get_model_settings()

    if purpose == ModelPurpose.TRIAGE:
        return init_chat_model(
            settings.triage_model,
            temperature=settings.triage_temperature,
            timeout=settings.triage_timeout_seconds,
            max_tokens=settings.triage_max_tokens,
            max_retries=settings.triage_max_retries,
        )

    raise ValueError(f"不支持的模型用途：{purpose}")
