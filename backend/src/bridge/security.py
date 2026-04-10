"""Bridge security — sender authorization."""

import logging

from src.bridge.models import InboundMessage

logger = logging.getLogger("mimir.bridge.security")


class BridgeSecurity:
    def __init__(self, config: dict):
        """Initialize with the 'security' sub-dict from bridge settings."""
        self._allowed = config.get("allowed_sender_ids", {})

    def is_authorized(self, message: InboundMessage) -> bool:
        """Check whether the sender is allowed.

        Empty allow-list for a platform = allow all (easy initial setup).
        Once any ID is configured, fail-closed: only listed IDs are permitted.
        """
        platform_ids = self._allowed.get(message.platform, [])
        if not platform_ids:
            return True
        authorized = message.sender_id in platform_ids
        if not authorized:
            logger.warning(
                f"Unauthorized sender {message.sender_id} on {message.platform}"
            )
        return authorized
