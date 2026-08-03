from functools import lru_cache
from importlib.resources import files


@lru_cache
def load_prompt(
    prompt_name: str,
    version: str,
    filename: str,
) -> str:
    path = (
        files("email_agent.prompts")
        .joinpath(prompt_name)
        .joinpath(version)
        .joinpath(filename)
    )

    return path.read_text(encoding="utf-8")
