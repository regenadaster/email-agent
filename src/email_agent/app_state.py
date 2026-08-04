from typing import Literal

from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    email_input: dict

    classification_decision: Literal[
        "ignore",
        "respond",
        "notify",
    ]

    classification_reason: str

    calendar_action: Literal[
        "none",
        "needs_clarification",
        "propose",
    ]

    calendar_draft: dict | None

    approval: Literal[
        "approve",
        "reject",
    ]

    event_id: str
    calendar_error: str | None
