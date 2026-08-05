from __future__ import annotations

import argparse
from uuid import uuid4

from dotenv import load_dotenv
from langgraph.types import Command

load_dotenv()
from email_agent.agent_server import create_graph
from email_agent.persistence import (
    create_checkpointer,
    setup_database,
)
from email_agent.settings import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--setup",
        action="store_true",
        help="初始化数据库表",
    )

    return parser.parse_args()


def main() -> None:
    """Start the application."""

    args = parse_args()
    settings = get_settings()

    if args.setup:
        setup_database(settings.database_url)
        print("数据库初始化完成")
        return

    with create_checkpointer(settings.database_url) as checkpointer:
        graph = create_graph(
            checkpointer=checkpointer,
        )

        config = {
            "configurable": {
                "thread_id": str(uuid4()),
            }
        }

        email_request = {
            "to": "Robert Xu <Robert@company.com>",
            "author": "Team Lead <teamlead@company.com>",
            "subject": "Quarterly planning meeting",
            "email_thread": (
                "The meeting is confirmed for August 5, 2026, "
                "from 10:00 AM to 11:30 AM, Asia/Beijing timezone. "
                "Location: Meeting Room A."
            ),
        }

        result = graph.invoke({"email_input": email_request}, config=config)

        interrupts = result.get("__interrupt__", [])

        if not interrupts:
            print(result)
            return

        approval_request = interrupts[0].value
        event = approval_request["event"]

        print("\n准备添加日历事项：")
        print("标题：", event["title"])
        print("开始：", event["start_time"])
        print("结束：", event["end_time"])
        print("地点：", event.get("location") or "无")

        answer = input("是否添加到日历？[y/N] ").strip().lower()

        decision = "approve" if answer in {"y", "yes"} else "reject"

        result = graph.invoke(
            Command(resume=decision),
            config=config,  # 必须是同一个 thread_id
        )

        print(result)


if __name__ == "__main__":
    main()
