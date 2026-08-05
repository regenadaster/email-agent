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
    classification_confidence: float

    calendar_action: Literal[
        "none",
        "needs_clarification",
        "propose",
    ]
    calendar_draft: dict | None
    calendar_available: bool | None
    calendar_conflicts: list[dict]

    reply_draft: dict | None
    clarification_question: str | None
    action_evidence: list[str]

    approval: Literal["approve", "reject"]
    event_id: str
    calendar_error: str | None
