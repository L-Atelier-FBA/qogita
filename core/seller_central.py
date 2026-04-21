from .requester import Requester
from datetime import datetime
import json
import asyncio
from .logger import get_logger

logger = get_logger("SellerCentral")


class SellerCentral:
    def __init__(self, cookie: str):
        self.country_code = "FR"
        self.locale = "fr-FR"
        self.cookie = cookie

    async def get_product_data(self, asin: str):
        url = (
            f"https://sellercentral-europe.amazon.com/rcpublic/productmatch?"
            f"searchKey={asin}&countryCode={self.country_code}&locale={self.locale}"
        )

        for attempt in range(5):
            try:
                async with Requester(
                    url=url,
                    referrer="https://sellercentral.amazon.fr/revcalpublic?lang=fr_FR",
                    api=True,
                    cookie=self.cookie
                ) as scraper:

                    output = await scraper.fetch_get()

                if not output or not getattr(output, "text", None):
                    await asyncio.sleep(1 + attempt * 0.5)
                    continue

                try:
                    data = json.loads(output.text)
                except json.JSONDecodeError:
                    await asyncio.sleep(1 + attempt * 0.5)
                    continue

                if data.get("succeed") is True:
                    products = (
                        data.get("data", {})
                        .get("otherProducts", {})
                        .get("products", [])
                    )

                    if not products:
                        return None, None, None, None, None, None

                    p = products[0]
                    return (
                        p.get("title"),
                        p.get("link"),
                        p.get("gl"),
                        p.get("salesRank"),
                        p.get("salesRankContextName"),
                        p.get("imageUrl"),
                    )

                await asyncio.sleep(1 + attempt * 0.5)

            except Exception as e:
                logger.warning(f"Product retry {attempt} failed {asin}: {e}")
                await asyncio.sleep(1 + attempt * 0.5)

        return None, None, None, None, None, None

    async def get_price(self, asin: str):
        url = (
            f"https://sellercentral-europe.amazon.com/rcpublic/getadditionalpronductinfo?"
            f"countryCode={self.country_code}&asin={asin}&fnsku=&searchType=GENERAL&locale={self.locale}"
        )

        for attempt in range(5):
            try:
                async with Requester(
                    url=url,
                    referrer="https://sellercentral.amazon.fr/revcalpublic?lang=fr_FR",
                    api=True,
                    cookie=self.cookie
                ) as scraper:

                    output = await scraper.fetch_get()

                if not output or not getattr(output, "text", None):
                    await asyncio.sleep(1 + attempt * 0.5)
                    continue

                try:
                    data = json.loads(output.text)
                except json.JSONDecodeError:
                    await asyncio.sleep(1 + attempt * 0.5)
                    continue

                price_data = data.get("data", {})
                price = price_data.get("price", {})

                price_amt = None

                if price and price.get("amount") is not None:
                    price_amt = float(price["amount"])

                await asyncio.sleep(1 + attempt * 0.5)

                return price_amt

            except Exception as e:
                logger.warning(f"Price retry {attempt} failed {asin}: {e}")
                await asyncio.sleep(1 + attempt * 0.5)

        return None

    async def get_fees(self, asin: str, gl: str, price: float):
        if not gl or price is None:
            return None

        url = (
            f"https://sellercentral-europe.amazon.com/rcpublic/getfees?"
            f"countryCode={self.country_code}&locale={self.locale}"
        )

        peak = datetime.now().month in [10, 11, 12]

        payload = {
            "countryCode": self.country_code,
            "itemInfo": {
                "asin": asin,
                "glProductGroupName": gl,
                "packageLength": "0",
                "packageWidth": "0",
                "packageHeight": "0",
                "dimensionUnit": "",
                "packageWeight": "0",
                "weightUnit": "",
                "afnPriceStr": str(price),
                "mfnPriceStr": str(price),
                "mfnShippingPriceStr": "0",
                "currency": "EUR",
                "isNewDefined": "false"
            },
            "programIdList": ["Core#0", "MFN#1"],
            "programParamMap": {}
        }

        for attempt in range(5):
            try:
                async with Requester(
                    url=url,
                    referrer="https://sellercentral.amazon.fr/revcalpublic?lang=fr_FR",
                    api=True,
                    cookie=self.cookie
                ) as scraper:

                    output = await scraper.fetch_post(payload)

                if not output or not getattr(output, "text", None):
                    await asyncio.sleep(1 + attempt * 0.5)
                    continue

                try:
                    data = json.loads(output.text)
                except json.JSONDecodeError:
                    await asyncio.sleep(1 + attempt * 0.5)
                    continue

                core = data.get("data", {}).get("programFeeResultMap", {}).get("Core#0", {})

                if not core:
                    await asyncio.sleep(1 + attempt * 0.5)
                    continue

                storage_fee = (
                    float(core.get("perUnitPeakStorageFee", {}).get("total", {}).get("amount", 0.0))
                    if peak
                    else float(core.get("perUnitNonPeakStorageFee", {}).get("total", {}).get("amount", 0.0))
                )

                fulfillment = float(core.get("otherFeeInfoMap", {}).get("FulfillmentFee", {}).get("total", {}).get("amount", 0.0))
                fixed = float(core.get("otherFeeInfoMap", {}).get("FixedClosingFee", {}).get("total", {}).get("amount", 0.0))
                referral = float(core.get("otherFeeInfoMap", {}).get("ReferralFee", {}).get("total", {}).get("amount", 0.0))
                variable = float(core.get("otherFeeInfoMap", {}).get("VariableClosingFee", {}).get("total", {}).get("amount", 0.0))
                digital = float(core.get("otherFeeInfoMap", {}).get("DigitalServicesFee", {}).get("total", {}).get("amount", 0.0))

                return round(fulfillment + referral + digital + storage_fee + fixed + variable, 2)

            except Exception as e:
                logger.warning(f"Fees retry {attempt} failed {asin}: {e}")
                await asyncio.sleep(1 + attempt * 0.5)

        return None

    @staticmethod
    async def get_sales(asin: str, rank: str, context: str):

        category = {
            "animalerie": 0,
            "auto et moto": 1,
            "bagages": 2,
            "beauté": 3,
            "beauté et parfum": 4,
            "bijoux": 5,
            "bricolage": 6,
            "bébé et puériculture": 7,
            "chaussures et sacs": 8,
            "commerce, industrie & science": 9,
            "cuisine & maison": 10,
            "dvd & blu-ray": 11,
            "épicerie": 12,
            "fournitures de bureau": 13,
            "gros électroménager": 14,
            "high-tech": 15,
            "hygiène et santé": 16,
            "informatique": 17,
            "instruments de musique": 18,
            "jardin": 19,
            "jeux et jouets": 20,
            "jeux vidéo": 21,
            "livres anglais et étrangers": 22,
            "livres": 23,
            "logiciels": 24,
            "luminaires et eclairage": 25,
            "mode": 26,
            "montres": 27,
            "sports et loisirs": 28,
            "vêtements et accessoires": 29,
            "vêtements": 30
        }

        if not context:
            logger.warning(f"{asin} - No context provided.")

        if not rank:
            logger.warning(f"{asin} - No rank provided.")

        url = f"https://amzscout.net/api/v2/landing/sales?domain=FR&categoryId={category[context.lower()]}&rank={rank}"

        try:
            async with Requester(
                    url=url,
                    referrer="https://amzscout.net/sales-estimator/",
                    api=True,
                ) as scraper:

                output = await scraper.fetch_get()

                try:
                    data = json.loads(output.text)
                    sales = data.get("sales", 0)
                    return int(sales)

                except json.JSONDecodeError:
                    return 0

        except Exception as e:
            logger.warning(f"Product sales scraping failed {asin}: {e}")

        return 0
