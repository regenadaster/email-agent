from uuid import uuid4

from dotenv import load_dotenv
from langgraph.types import Command


def main() -> None:
    """Start the application."""
    load_dotenv()

    # 这一句放在后面，保障openai和langsmith环境变量等先加载完
    from email_agent.agent_server import graph

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
