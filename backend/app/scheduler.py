"""Background scheduler for periodic Google Drive sync.

Runs as an asyncio background task started from ``main.py`` lifespan.
Only active when ``settings.drive_enabled`` is True.
"""

import asyncio
import logging

from app.config import settings
from app.database import SessionLocal
from app.drive_sync import sync_and_analyze

logger = logging.getLogger(__name__)


async def run_sync_loop() -> None:
    """Periodically sync images from Google Drive and run analysis.

    Runs indefinitely, sleeping ``drive_sync_interval_minutes`` between cycles.
    """
    interval = settings.drive_sync_interval_minutes * 60
    logger.info(
        "Drive sync scheduler started (interval=%d min)",
        settings.drive_sync_interval_minutes,
    )

    # Wait a few seconds before the first sync so the server can finish starting
    await asyncio.sleep(5)

    while True:
        try:
            db = SessionLocal()
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, sync_and_analyze, db
                )
                logger.info("Scheduled sync result: %s", result)
            finally:
                db.close()
        except Exception:
            logger.exception("Error in scheduled Drive sync")

        await asyncio.sleep(interval)
