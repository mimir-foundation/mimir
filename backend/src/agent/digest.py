"""Weekly digest email — summarizes the week's activity and sends via SMTP."""

import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.knowledge import database as db
from src.knowledge.models import new_id

logger = logging.getLogger("mimir.agent.digest")


async def generate_digest() -> dict | None:
    """Build weekly digest content from the past 7 days."""
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    # Notes captured this week
    notes = await db.fetch_all(
        "SELECT id, title, source_type, created_at FROM notes WHERE created_at >= ? ORDER BY created_at DESC",
        (week_ago,),
    )

    # Connections found this week
    connections = await db.fetch_all(
        "SELECT c.connection_type, c.strength, c.explanation, "
        "n1.title as source_title, n2.title as target_title "
        "FROM connections c "
        "JOIN notes n1 ON n1.id = c.source_note_id "
        "JOIN notes n2 ON n2.id = c.target_note_id "
        "WHERE c.created_at >= ? ORDER BY c.strength DESC LIMIT 10",
        (week_ago,),
    )

    # Top concepts by note count
    top_concepts = await db.fetch_all(
        "SELECT c.name, COUNT(nc.note_id) as cnt FROM concepts c "
        "JOIN note_concepts nc ON c.id = nc.concept_id "
        "JOIN notes n ON n.id = nc.note_id "
        "WHERE n.created_at >= ? "
        "GROUP BY c.id ORDER BY cnt DESC LIMIT 10",
        (week_ago,),
    )

    # Totals
    total_notes = await db.fetch_one("SELECT COUNT(*) as cnt FROM notes")
    total_concepts = await db.fetch_one("SELECT COUNT(*) as cnt FROM concepts")
    total_connections = await db.fetch_one("SELECT COUNT(*) as cnt FROM connections")

    return {
        "notes": [dict(n) for n in notes],
        "connections": [dict(c) for c in connections],
        "top_concepts": [dict(c) for c in top_concepts],
        "total_notes": total_notes["cnt"] if total_notes else 0,
        "total_concepts": total_concepts["cnt"] if total_concepts else 0,
        "total_connections": total_connections["cnt"] if total_connections else 0,
        "notes_this_week": len(notes),
        "connections_this_week": len(connections),
    }


def _build_html(digest: dict) -> str:
    """Build HTML email body from digest data."""
    notes = digest["notes"]
    connections = digest["connections"]
    concepts = digest["top_concepts"]

    notes_html = ""
    for n in notes[:20]:
        title = n.get("title") or "Untitled"
        source = n.get("source_type", "")
        date = (n.get("created_at") or "")[:10]
        notes_html += f"<li><strong>{title}</strong> <span style='color:#888'>({source}, {date})</span></li>\n"

    connections_html = ""
    for c in connections[:10]:
        connections_html += (
            f"<li><strong>{c.get('source_title', '?')}</strong> &harr; "
            f"<strong>{c.get('target_title', '?')}</strong> "
            f"<span style='color:#888'>({c.get('connection_type', '')}, "
            f"strength: {c.get('strength', 0):.2f})</span></li>\n"
        )

    concepts_html = ""
    for c in concepts:
        concepts_html += f"<li>{c['name']} ({c['cnt']} notes)</li>\n"

    return f"""
    <html>
    <body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
        <h1 style="color: #4f46e5;">Mimir Weekly Digest</h1>
        <p style="color: #666;">Week ending {datetime.utcnow().strftime('%B %d, %Y')}</p>

        <h2>Summary</h2>
        <table style="border-collapse: collapse;">
            <tr><td style="padding: 4px 16px 4px 0;">Notes captured this week</td><td><strong>{digest['notes_this_week']}</strong></td></tr>
            <tr><td style="padding: 4px 16px 4px 0;">Connections found</td><td><strong>{digest['connections_this_week']}</strong></td></tr>
            <tr><td style="padding: 4px 16px 4px 0;">Total notes</td><td><strong>{digest['total_notes']}</strong></td></tr>
            <tr><td style="padding: 4px 16px 4px 0;">Total concepts</td><td><strong>{digest['total_concepts']}</strong></td></tr>
            <tr><td style="padding: 4px 16px 4px 0;">Total connections</td><td><strong>{digest['total_connections']}</strong></td></tr>
        </table>

        {f'<h2>Recent Notes</h2><ul>{notes_html}</ul>' if notes_html else ''}
        {f'<h2>New Connections</h2><ul>{connections_html}</ul>' if connections_html else ''}
        {f'<h2>Top Concepts</h2><ul>{concepts_html}</ul>' if concepts_html else ''}

        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
        <p style="color: #999; font-size: 12px;">Sent by Mimir &mdash; your AI second brain</p>
    </body>
    </html>
    """


async def send_digest() -> bool:
    """Generate and send the weekly digest email."""
    from src.config import get_settings
    settings = get_settings()

    if not settings.smtp_host or not settings.smtp_recipient:
        logger.info("SMTP not configured — skipping digest")
        return False

    digest = await generate_digest()
    if not digest:
        return False

    html = _build_html(digest)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Mimir Weekly Digest — {datetime.utcnow().strftime('%B %d, %Y')}"
    msg["From"] = settings.smtp_from or settings.smtp_user or "mimir@localhost"
    msg["To"] = settings.smtp_recipient
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [settings.smtp_recipient], msg.as_string())
        logger.info(f"Weekly digest sent to {settings.smtp_recipient}")

        # Log to agent_log
        await db.execute(
            "INSERT INTO agent_log (id, action_type, details, started_at, completed_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            (new_id(), "weekly_digest", f'{{"recipient": "{settings.smtp_recipient}", "notes": {digest["notes_this_week"]}}}',
             datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), "complete"),
        )
        return True

    except Exception as e:
        logger.error(f"Failed to send digest: {e}", exc_info=True)
        await db.execute(
            "INSERT INTO agent_log (id, action_type, details, started_at, completed_at, status, error_message) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id(), "weekly_digest", "{}", datetime.utcnow().isoformat(),
             datetime.utcnow().isoformat(), "error", str(e)),
        )
        return False
