"""Notification webhooks — deliver briefs and alerts to external services."""

import json
import logging

import httpx

from src.knowledge import database as db

logger = logging.getLogger("mimir.agent.notifications")


async def send_webhook(content: str, title: str = "Mimir") -> bool:
    """Send content to the configured webhook URL.

    Supports: generic JSON, Mattermost, Slack, ntfy, Discord.
    """
    settings = await db.fetch_one("SELECT value FROM settings WHERE key = 'notifications'")
    if not settings:
        return False

    try:
        config = json.loads(settings["value"])
    except (json.JSONDecodeError, TypeError):
        return False

    webhook_url = config.get("webhook_url")
    webhook_type = config.get("webhook_type", "generic")

    if not webhook_url:
        return False

    try:
        payload = _build_payload(content, title, webhook_type)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        logger.info(f"Webhook sent to {webhook_type}: {resp.status_code}")
        return True
    except Exception as e:
        logger.error(f"Webhook delivery failed: {e}")
        return False


def _build_payload(content: str, title: str, webhook_type: str) -> dict:
    if webhook_type == "mattermost":
        return {"text": f"### {title}\n\n{content}"}

    elif webhook_type == "slack":
        return {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": title}},
                {"type": "section", "text": {"type": "mrkdwn", "text": content}},
            ]
        }

    elif webhook_type == "discord":
        return {
            "embeds": [{
                "title": title,
                "description": content[:4096],
                "color": 6366961,  # indigo
            }]
        }

    elif webhook_type == "ntfy":
        return {
            "topic": title.lower().replace(" ", "-"),
            "title": title,
            "message": content,
        }

    else:  # generic
        return {"title": title, "content": content}


async def send_brief_notification(brief_content: str) -> bool:
    """Send the daily brief via webhook."""
    success = await send_webhook(brief_content, title="Mimir Daily Brief")
    if success:
        # Mark brief as delivered via webhook
        await db.execute(
            """UPDATE daily_briefs SET delivered_webhook = 1
               WHERE brief_date = (SELECT MAX(brief_date) FROM daily_briefs)"""
        )
    return success


async def send_resurface_notification(reason: str, note_title: str) -> bool:
    """Send a resurface alert via webhook."""
    content = f"**{note_title}**\n\n{reason}"
    return await send_webhook(content, title="Mimir Resurface")
