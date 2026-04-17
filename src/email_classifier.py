import json
import re
import time
from typing import Literal

import anthropic
import yaml
from pydantic import BaseModel


# --- Interface contract ---
VALID_CATEGORIES = ("billing", "technical", "account", "general", "feature_request", "security")

class EmailClassification(BaseModel):
    category: Literal["billing", "technical", "account", "general", "feature_request", "security"]
    summary: str


class PromptConfig(BaseModel):
    version: str
    timestamp: str
    system_prompt: str
    examples: list


# --- Prompt loader ---
def load_prompt_config(prompt_path: str) -> PromptConfig:
    """Load and validate a prompt configuration from a YAML file."""
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PromptConfig(**data)


# --- Response parser (robust) ---
def _parse_classification(raw_text: str) -> dict:
    """
    Parse model output into {category, summary}.
    Tries JSON first, then regex fallback.
    """
    # Attempt 1: direct JSON parse
    try:
        result = json.loads(raw_text.strip())
        if "category" in result and "summary" in result:
            return result
    except (json.JSONDecodeError, TypeError):
        pass

    # Attempt 2: extract JSON block from markdown fences
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group(1))
            if "category" in result and "summary" in result:
                return result
        except (json.JSONDecodeError, TypeError):
            pass

    # Attempt 3: find any JSON object in the text
    brace_match = re.search(r"\{[^{}]*\"category\"[^{}]*\}", raw_text, re.DOTALL)
    if brace_match:
        try:
            result = json.loads(brace_match.group(0))
            if "category" in result and "summary" in result:
                return result
        except (json.JSONDecodeError, TypeError):
            pass

    # Attempt 4: regex extraction
    cat_match = re.search(r"[\"']?category[\"']?\s*[:=]\s*[\"'](\w+)[\"']", raw_text, re.IGNORECASE)
    sum_match = re.search(r"[\"']?summary[\"']?\s*[:=]\s*[\"'](.+?)[\"']", raw_text, re.IGNORECASE)
    if cat_match:
        return {
            "category": cat_match.group(1).lower(),
            "summary": sum_match.group(1) if sum_match else "No summary extracted."
        }

    raise ValueError(f"Could not parse classification from model output: {raw_text[:200]}")


# --- Main classifier ---
def classify_email(
    email_text: str,
    prompt_config: PromptConfig,
    anthropic_api_key: str,
    model: str = "claude-sonnet-4-20250514",
    max_retries: int = 2,
) -> EmailClassification:
    """
    Classify and summarize a customer support email using Claude.

    Args:
        email_text: The raw email text to classify.
        prompt_config: Loaded prompt configuration with system prompt and examples.
        anthropic_api_key: Anthropic API key.
        model: Claude model identifier.
        max_retries: Number of retries on transient failures.

    Returns:
        EmailClassification with category and summary.
    """


    # Build the user prompt with few-shot examples
    user_prompt = ""
    for ex in prompt_config.examples:
        user_prompt += (
            f"Email: {ex['input']}\n"
            f"Response: {{\"category\": \"{ex['category']}\", \"summary\": \"{ex['summary']}\"}}\n\n"
        )
    user_prompt += f"Email: {email_text}\nResponse:"

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=256,
                temperature=0,
                system=prompt_config.system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = message.content[0].text
            parsed = _parse_classification(raw_text)

            # Normalize category
            category = parsed["category"].strip().lower()
            if category not in VALID_CATEGORIES:
                category = "general"  # fallback for unknown categories

            return EmailClassification(category=category, summary=parsed["summary"])

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.5 * attempt)  # exponential-ish backoff
                continue
            break

    raise ValueError(
        f"Failed to classify email after {max_retries} attempts. "
        f"Last error: {last_error}"
    )
