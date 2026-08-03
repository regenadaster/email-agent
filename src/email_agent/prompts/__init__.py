from email_agent.prompts.loader import load_prompt

TRIAGE_PROMPT_NAME = "triage"
TRIAGE_PROMPT_VERSION = "v1"

TRIAGE_SYSTEM_PROMPT = load_prompt(
    prompt_name=TRIAGE_PROMPT_NAME,
    version=TRIAGE_PROMPT_VERSION,
    filename="system.md",
)
