"""Amazon Bedrock-powered insight generation."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from marketpulse.core.config import get_settings

logger = logging.getLogger(__name__)

MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
ANTHROPIC_VERSION = "bedrock-2023-05-31"


def _bedrock_client():
    settings = get_settings()
    kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if settings.bedrock_endpoint_url:
        kwargs["endpoint_url"] = settings.bedrock_endpoint_url
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
    if settings.aws_secret_access_key:
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if settings.aws_session_token:
        kwargs["aws_session_token"] = settings.aws_session_token
    return boto3.client("bedrock-runtime", **kwargs)


def _compact(value: Any) -> str:
    try:
        return json.dumps(value, default=str, ensure_ascii=True)[:4000]
    except Exception:
        return str(value)[:4000]


def _fallback_message(category: str, decision_data: Any) -> str:
    decision: Mapping[str, Any] = decision_data if isinstance(decision_data, Mapping) else {}
    action = str(decision.get("recommended_action", "MONITOR")).replace("_", " ").title()
    order_qty = decision.get("order_quantity", 0)
    risk_score = decision.get("risk_score", "unknown")

    return (
        f"{category} has elevated stock risk right now, especially around local demand changes and seasonal events. "
        f"Please {action.lower()} and plan approximately {order_qty} units based on current estimates. "
        f"Recheck inventory and sales trend within 24 hours (risk score: {risk_score})."
    )


def generate_category_insight(
    category: str,
    forecast_data: Any,
    decision_data: Any,
    festival_context: Any,
) -> str:
    """Generate a 3-sentence actionable category insight using Bedrock Claude."""
    settings = get_settings()
    if settings.mock_bedrock:
        return (
            f"{category} is showing near-term demand risk driven by trend and upcoming festival effects. "
            "Demand is expected to rise versus current baseline in the next ordering window. "
            "Increase purchase quantity now and place the order before lead-time cutoff to reduce stockout risk."
        )

    prompt = f"""
You are an inventory advisor for a small Indian retail store owner.

Write exactly 3 sentences in simple language with no jargon.
Sentence 1: Explain the current risk clearly.
Sentence 2: Explain why this is happening using demand trend and festival context.
Sentence 3: Give a specific action with quantity/timeline and by-when guidance.

Keep it practical and actionable.

Category: {category}
Forecast Data: {_compact(forecast_data)}
Decision Data: {_compact(decision_data)}
Festival Context: {_compact(festival_context)}
"""

    payload = {
        "anthropic_version": ANTHROPIC_VERSION,
        "max_tokens": 220,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt.strip()}],
            }
        ],
    }

    try:
        response = _bedrock_client().invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload),
        )
        body = json.loads(response["body"].read())
        content = body.get("content", [])
        text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
        insight = " ".join(part.strip() for part in text_parts if part.strip()).strip()
        if not insight:
            logger.warning("Bedrock returned empty insight for category=%s", category)
            return _fallback_message(category, decision_data)
        return insight
    except (ClientError, BotoCoreError, ValueError, KeyError, json.JSONDecodeError):
        logger.exception("Bedrock insight generation failed for category=%s", category)
        return _fallback_message(category, decision_data)
