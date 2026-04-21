import os
import asyncio
import random
import aiohttp
import math
from core.discord_sender import DiscordSender
from core.logger import get_logger
from dotenv import load_dotenv
from core.database import Database

load_dotenv()
logger = get_logger("Poster")

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

MIN_DELAY = 15
MAX_DELAY = 30


async def main():
    if not WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK not set.")
        return

    logger.info("Starting poster run.")

    db = Database()
    deals = await db.get_unposted_deals(limit=1000)

    if not deals:
        logger.info("No deals found.")
        return

    max_posts = len(deals) if len(deals) <= 100 else math.ceil(len(deals) / 5)

    to_post = deals[:max_posts]

    logger.info(f"Posting {len(to_post)} deals")

    async with aiohttp.ClientSession() as session:
        sender = DiscordSender(WEBHOOK_URL, session)

        for deal in to_post:
            try:
                success = await sender.send_deal(deal)

                if success:
                    await db.mark_as_posted(deal["asin"])
                    logger.info(f"Posted {deal['asin']}")

            except Exception as e:
                logger.exception(f"Failed {deal.get('asin')} - {e}")

            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            await asyncio.sleep(delay)

    logger.info("Finished run")


if __name__ == "__main__":
    asyncio.run(main())