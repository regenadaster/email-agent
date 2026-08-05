from __future__ import annotations

from contextlib import AbstractContextManager

from langgraph.checkpoint.postgres import PostgresSaver


def create_checkpointer(
    database_url: str,
) -> AbstractContextManager[PostgresSaver]:
    """
    创建运行时使用的 LangGraph PostgreSQL checkpointer。

    使用方式：
        with create_checkpointer(database_url) as checkpointer:
            graph = create_graph(checkpointer=checkpointer)
    """
    return PostgresSaver.from_conn_string(database_url)


def setup_database(database_url: str) -> None:
    """
    初始化 LangGraph checkpoint 表和 email-agent 业务表。

    只需要在首次部署或数据库结构升级时执行。
    """
    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        # 创建 LangGraph checkpoint 相关表
        checkpointer.setup()

        # 复用 checkpointer 当前持有的 PostgreSQL 连接
        connection = checkpointer.conn

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS email_workflows (
                id UUID PRIMARY KEY,

                email_key VARCHAR(128) NOT NULL UNIQUE,
                email_input JSONB NOT NULL,

                thread_id VARCHAR(128) NOT NULL UNIQUE,

                status VARCHAR(32) NOT NULL,

                interrupt_payload JSONB,
                approval_decision VARCHAR(16),

                retry_count INTEGER NOT NULL DEFAULT 0,
                next_retry_at TIMESTAMPTZ,
                last_error TEXT,

                locked_until TIMESTAMPTZ,

                calendar_action_key VARCHAR(128),
                calendar_action_status VARCHAR(32)
                    NOT NULL DEFAULT 'NOT_STARTED',
                calendar_event_id VARCHAR(512),

                created_at TIMESTAMPTZ
                    NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ
                    NOT NULL DEFAULT now(),
                completed_at TIMESTAMPTZ
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_email_workflows_pending
            ON email_workflows (
                status,
                next_retry_at
            )
            """
        )
