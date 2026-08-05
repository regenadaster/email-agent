from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """email-agent 应用配置。"""

    # 对应环境变量 DATABASE_URL
    database_url: str

    model_config = SettingsConfigDict(
        # 本地开发时读取项目根目录的 .env
        env_file=".env",
        env_file_encoding="utf-8",
        # 环境变量名称不区分大小写：
        # DATABASE_URL 和 database_url 都能识别
        case_sensitive=False,
        # .env 中存在其他配置时不报错
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """读取并缓存应用配置。"""
    return Settings()
