import aiohttp
from .logger import get_logger

logger = get_logger("DiscordSender")


class DiscordSender:
    def __init__(self, webhook_url: str, session: aiohttp.ClientSession):
        self.webhook_url = webhook_url
        self.session = session

    @staticmethod
    def roi_color(roi: float) -> int:
        if roi >= 60:
            return 0x00FF00
        if roi >= 40:
            return 0x2ECC71
        if roi >= 25:
            return 0xF1C40F
        return 0xE74C3C

    async def send_deal(self, deal: dict):
        try:
            embed = {
                "title": f"**{deal.get('name','')}**",
                "color": self.roi_color(deal.get("roi", 0)),
                "thumbnail": {"url": deal.get("image_url", "")},
                "fields": [
                    {"name": "EAN", "value": deal.get("ean", ""), "inline": False},
                    {"name": "ASIN", "value": deal.get("asin", ""), "inline": False},
                    {"name": "Supplier", "value": f"€{deal.get('supplier_cost',0):.2f}", "inline": False},
                    {"name": "Amazon", "value": f"€{deal.get('amazon_price',0):.2f}", "inline": False},
                    {"name": "Fees", "value": f"€{deal.get('fees',0):.2f}", "inline": False},
                    {"name": "Profit", "value": f"€{deal.get('profit',0):.2f}", "inline": False},
                    {"name": "ROI", "value": f"{deal.get('roi',0):.2f}%", "inline": False},
                    {"name": "Sales", "value": str(deal.get('estimated_sales', 0)), "inline": False},
                    {
                        "name": "Links",
                        "value": f"[Amazon]({deal.get('amazon_link','')}) | [Qogita]({deal.get('supplier_link','')}) | [SAS]({deal.get('sas_link','')})",
                        "inline": False,
                    },
                ],
            }

            async with self.session.post(self.webhook_url, json={"embeds": [embed]}) as r:
                if r.status in (200, 204):
                    return True

                logger.error(await r.text())
                return False

        except Exception as e:
            logger.error(str(e))
            return False