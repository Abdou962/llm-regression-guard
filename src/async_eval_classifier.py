"""
Async evaluation classifier — runs the email classifier on the golden dataset
using async I/O for parallel processing with LLM-as-judge scoring.
"""
import asyncio
import json
import os
import sys
import time

# Ensure project root is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import anthropic
from dotenv import load_dotenv

from src.email_classifier import VALID_CATEGORIES, PromptConfig, load_prompt_config

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

BATCH_SIZE = 5


async def classify_email_async(client, email_text: str, prompt_config: PromptConfig) -> dict:
    """Classify a single email asynchronously using Claude."""
    user_prompt = ""
    for ex in prompt_config.examples:
        user_prompt += (
            f"Email: {ex['input']}\n"
            f"Response: {{\"category\": \"{ex['category']}\", \"summary\": \"{ex['summary']}\"}}\n\n"
        )
    user_prompt += f"Email: {email_text}\nResponse:"

    start = time.perf_counter()
    try:
        message = await client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=256,
            temperature=0,
            system=prompt_config.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        latency = time.perf_counter() - start

        try:
            parsed = json.loads(message.content[0].text)
            category = parsed.get("category", "").strip().lower()
            if category not in VALID_CATEGORIES:
                category = "general"
            summary = parsed.get("summary", "")
        except (json.JSONDecodeError, TypeError):
            category = ""
            summary = ""

        token_usage = None
        if hasattr(message, "usage") and message.usage:
            token_usage = {
                "input_tokens": getattr(message.usage, "input_tokens", 0),
                "output_tokens": getattr(message.usage, "output_tokens", 0),
            }

        return {
            "raw_output": message.content[0].text,
            "category": category,
            "summary": summary,
            "latency": round(latency, 3),
            "token_usage": token_usage,
        }
    except Exception as e:
        latency = time.perf_counter() - start
        return {
            "raw_output": f"ERROR: {e}",
            "category": "",
            "summary": "",
            "latency": round(latency, 3),
            "token_usage": None,
        }


async def judge_summary_async(client, email_text: str, expected_summary: str, predicted_summary: str) -> int | None:
    """Use LLM-as-judge to score summary relevance (1-5)."""
    judge_prompt = (
        "You are a strict evaluator. Given a customer email, a reference summary, and a predicted summary, "
        "rate the predicted summary's relevance and faithfulness to the reference on a scale from 1 (bad) to 5 (perfect). "
        "Only output a single integer (1-5).\n"
        f"Email: {email_text}\n"
        f"Reference summary: {expected_summary}\n"
        f"Predicted summary: {predicted_summary}\n"
        f"Score:"
    )
    try:
        message = await client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=10,
            temperature=0,
            system="You are a strict evaluator for summary relevance. Output only a single integer 1-5.",
            messages=[{"role": "user", "content": judge_prompt}],
        )
        score_str = message.content[0].text.strip().split()[0]
        return int(score_str) if score_str.isdigit() else None
    except Exception:
        return None


async def run_batch(client, batch: list, prompt_config: PromptConfig) -> tuple:
    """Run classification and judging for a batch of cases."""
    # Classify in parallel
    classify_tasks = [
        classify_email_async(client, case.get("input") or "", prompt_config)
        for case in batch
    ]
    results = await asyncio.gather(*classify_tasks)

    # Judge summaries in parallel
    judge_tasks = []
    for case, r in zip(batch, results, strict=True):
        if r["summary"]:
            judge_tasks.append(
                judge_summary_async(
                    client,
                    case.get("input") or "",
                    case["expected_output"]["summary"],
                    r["summary"],
                )
            )
        else:
            judge_tasks.append(asyncio.coroutine(lambda: None)() if sys.version_info < (3, 11) else asyncio.sleep(0, result=None))

    judge_scores = await asyncio.gather(*judge_tasks)
    return results, judge_scores


async def main():
    """Main async entry point."""
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key or anthropic_api_key.startswith("sk-<"):
        print("[ERROR] Set a valid ANTHROPIC_API_KEY in .env to use async evaluation.")
        sys.exit(1)

    dataset_path = os.path.join(PROJECT_ROOT, "data", "golden_dataset_v1.json")
    prompt_path = os.path.join(PROJECT_ROOT, "prompts", "v1_billing_classifier.yaml")

    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    prompt_config = load_prompt_config(prompt_path)
    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    all_results = []
    total_batches = (len(dataset) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(dataset), BATCH_SIZE):
        batch = dataset[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        outputs, judge_scores = await run_batch(client, batch, prompt_config)

        for case, output, judge_score in zip(batch, outputs, judge_scores, strict=True):
            expected = case["expected_output"]
            category_match = output["category"].strip().lower() == expected["category"].strip().lower()

            all_results.append({
                "id": case["id"],
                "input": case.get("input"),
                "expected_output": expected,
                "category": output["category"],
                "summary": output["summary"],
                "category_match": category_match,
                "summary_judge_score": judge_score,
                "latency": output["latency"],
                "token_usage": output["token_usage"],
                "raw_output": output["raw_output"],
                "expected_difficulty": case.get("expected_difficulty", ""),
                "notes": case.get("notes", ""),
            })

        print(f"  Batch {batch_num}/{total_batches}: {len(batch)} cases processed.")

    # Save raw outputs
    output_path = os.path.join(PROJECT_ROOT, "data", "raw_outputs.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    pass_count = sum(1 for r in all_results if r["category_match"])
    avg_latency = sum(r["latency"] for r in all_results) / len(all_results) if all_results else 0
    judge_scores_valid = [r["summary_judge_score"] for r in all_results if r["summary_judge_score"] is not None]
    avg_judge = sum(judge_scores_valid) / len(judge_scores_valid) if judge_scores_valid else 0

    print(f"\nDone: {pass_count}/{len(all_results)} passed ({pass_count / len(all_results):.1%})")
    print(f"Avg latency: {avg_latency:.2f}s | Avg judge score: {avg_judge:.1f}/5")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
