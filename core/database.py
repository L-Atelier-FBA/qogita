import os
import json
import asyncio
from datetime import datetime, timezone
from .logger import get_logger

logger = get_logger("Database")

DB_PATH = "data/deals.json"


class Database:
    def __init__(self):
        os.makedirs("data", exist_ok=True)

        if not os.path.exists(DB_PATH):
            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump([], f)

        self._lock = asyncio.Lock()

    @staticmethod
    async def _read_all_unlocked():
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.error("Database reset due to corruption")
            return []

    @staticmethod
    async def _write_all_unlocked(data):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def save_deal(self, deal: dict):
        async with self._lock:
            deals = await self._read_all_unlocked()

            asin = deal.get("asin")
            ean = deal.get("ean")

            for d in deals:
                if d.get("asin") == asin or d.get("ean") == ean:
                    return False

            deal["posted"] = False
            deal["posted_at"] = None
            deal["created_at"] = datetime.now(timezone.utc).isoformat()

            deals.append(deal)
            await self._write_all_unlocked(deals)

            return True

    async def get_unposted_deals(self, limit: int):
        async with self._lock:
            deals = await self._read_all_unlocked()

        unposted = [d for d in deals if not d.get("posted")]
        unposted.sort(key=lambda x: x.get("created_at", ""))

        return unposted[:limit]

    async def mark_as_posted(self, asin: str):
        async with self._lock:
            deals = await self._read_all_unlocked()

            for d in deals:
                if d.get("asin") == asin:
                    d["posted"] = True
                    d["posted_at"] = datetime.now(timezone.utc).isoformat()
                    break

            await self._write_all_unlocked(deals)

    @staticmethod
    async def reset_db():
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)