"""Prompt-configurable customer support email classifier."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

Category = Literal["billing", "technical", "account", "general"]


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Category
    summary: str = Field(min_length=1, max_length=240)


class PromptConfig(BaseModel):
    version: str
    created_at: str
    system_prompt: str = Field(min_length=1)
    few_shot_examples: list[dict[str, str]] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, obj, **kwargs):
        config = super().model_validate(obj, **kwargs)
        if not config.version.strip() or not config.created_at.strip():
            raise ValueError("prompt version and created_at must not be empty")
        for index, example in enumerate(config.few_shot_examples):
            if not example.get("input", "").strip() or not example.get("output", "").strip():
                raise ValueError(f"few_shot_examples[{index}] requires non-empty input and output")
        return config

    @classmethod
    def load(cls, path: Path) -> "PromptConfig":
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def classify_email(email_text: str, prompt: PromptConfig, model: str = "gpt-4o-mini") -> Classification:
    """Classify one email using the configured prompt and OpenAI structured output."""
    if not email_text.strip():
        raise ValueError("email_text must not be empty")
    from openai import OpenAI

    examples = "\n\nFew-shot examples:\n" + "\n".join(
        f"Email: {item['input']}\nOutput: {item['output']}" for item in prompt.few_shot_examples
    ) if prompt.few_shot_examples else ""
    response = OpenAI().responses.parse(
        model=model,
        input=[
            {"role": "system", "content": prompt.system_prompt + examples},
            {"role": "user", "content": email_text},
        ],
        text_format=Classification,
    )
    if response.output_parsed is None:
        raise RuntimeError("Model did not return a structured classification")
    return response.output_parsed
