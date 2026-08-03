from dotenv import load_dotenv


def main() -> None:
    """Start the application."""
    load_dotenv()

    # 这一句放在后面，保障openai和langsmith环境变量等先加载完
    from email_agent.agent_server import graph

    print("Agent Demo started successfully.")

    email_request = {
        "to": "Robert Xu <Robert@company.com>",
        "author": "Team Lead <teamlead@company.com>",
        "subject": "Quarterly planning meeting",
        "email_thread": "Hi Robert,\n\nIt's time for our quarterly planning session. I'd like to schedule a 90-minute meeting next week to discuss our roadmap for Q3.\n\nCould you let me know your availability for Monday or Wednesday? Ideally sometime between 10AM and 3PM.\n\nLooking forward to your input on the new feature priorities.\n\nBest,\nTeam Lead",
    }

    result = graph.invoke({"email_input": email_request})
    print(result)


if __name__ == "__main__":
    main()
