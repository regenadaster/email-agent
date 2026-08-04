from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelSettings(BaseSettings):
    """模型相关配置。"""

    model_config = SettingsConfigDict(
        env_prefix="EMAIL_AGENT_",
        case_sensitive=False,
        extra="ignore",
    )

    triage_model: str = "openai:gpt-5.5"
    triage_temperature: float = 0.0
    triage_timeout_seconds: float = 300
    triage_max_tokens: int = 2000
    triage_max_retries: int = 3


@cache
def get_model_settings() -> ModelSettings:
    return ModelSettings()
