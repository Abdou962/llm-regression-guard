import json
import os
import re
from typing import Any

import yaml


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_yaml(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_prompt_metadata(prompt_path: str) -> tuple[str, str]:
    try:
        prompt = load_yaml(prompt_path)
        version = prompt.get("version", "unknown")
        timestamp = prompt.get("timestamp", prompt.get("date", "unknown"))
        return version, timestamp
    except Exception as e:
        print(f"Warning: Cannot read prompt file - {e}")
        return "unknown", "unknown"


def extract_model_from_results(raw_outputs_path: str) -> str:
    try:
        data = load_json(raw_outputs_path)
        if not data:
            return "unknown"
        for item in data[:10]:
            usage = item.get("token_usage")
            if usage and isinstance(usage, dict):
                if "model" in usage:
                    return usage["model"]
                if "model_name" in usage:
                    return usage["model_name"]
            raw = item.get("raw_output", "")
            if isinstance(raw, str):
                match = re.search(r'"model"\s*:\s*"([^\"]+)"', raw)
                if match:
                    return match.group(1)
                match = re.search(r"model[=\s]+([a-zA-Z0-9\-_\.]+)", raw)
                if match:
                    return match.group(1)
        return "unknown"
    except Exception as e:
        print(f"Warning: Cannot extract model - {e}")
        return "unknown"


def update_trend_history(trend_path: str, run_data: dict[str, Any]) -> list[dict[str, Any]]:
    history = []
    if os.path.exists(trend_path):
        try:
            history = load_json(trend_path)
        except (json.JSONDecodeError, OSError):
            history = []
    history.append(run_data)
    history = history[-20:]
    save_json(trend_path, history)
    return history
