# action/schemas.py

from pydantic import BaseModel, Field

from email_agent.triage.schemas import CalendarDraft


class ReplyDraft(BaseModel):
    to: list[str]
    cc: list[str] = Field(default_factory=list)
    subject: str
    body: str
    rationale: str


class ActionPlan(BaseModel):
    reply_draft: ReplyDraft | None = None
    calendar_draft: CalendarDraft | None = None

    calendar_available: bool | None = None
    calendar_conflicts: list[dict] = Field(default_factory=list)

    clarification_question: str | None = None
    evidence: list[str] = Field(default_factory=list)
