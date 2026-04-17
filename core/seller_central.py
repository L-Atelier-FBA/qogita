from .requester import Requester
from datetime import datetime
import json
import asyncio
from .logger import get_logger

logger = get_logger("SellerCentral")


class SellerCentral:
    def __init__(self, cookie: str):
        self.country_code = "FR"
        self.locale = "en-GB"
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
                    referrer="https://sellercentral-europe.amazon.com/fba/profitabilitycalculator/index?lang=en_GB",
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
                        return None, None, None, None

                    p = products[0]
                    return (
                        p.get("title"),
                        p.get("link"),
                        p.get("gl"),
                        p.get("imageUrl"),
                    )

                await asyncio.sleep(1 + attempt * 0.5)

            except Exception as e:
                logger.warning(f"Product retry {attempt} failed {asin}: {e}")
                await asyncio.sleep(1 + attempt * 0.5)

        return None, None, None, None

    async def get_price(self, asin: str):
        url = (
            f"https://sellercentral-europe.amazon.com/rcpublic/getadditionalpronductinfo?"
            f"countryCode={self.country_code}&asin={asin}&fnsku=&searchType=GENERAL&locale={self.locale}"
        )

        for attempt in range(5):
            try:
                async with Requester(
                    url=url,
                    referrer="https://sellercentral-europe.amazon.com/fba/profitabilitycalculator/index?lang=en_GB",
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

                if price and price.get("amount") is not None:
                    return float(price["amount"])

                await asyncio.sleep(1 + attempt * 0.5)

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
                    referrer="https://sellercentral-europe.amazon.com/fba/profitabilitycalculator/index?lang=en_GB",
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

                #storage_fee = (
                #    float(core.get("perUnitPeakStorageFee", {}).get("total", {}).get("amount", 0.0))
                #    if peak
                #    else float(core.get("perUnitNonPeakStorageFee", {}).get("total", {}).get("amount", 0.0))
                #)

                fulfillment = float(core.get("otherFeeInfoMap", {}).get("FulfillmentFee", {}).get("total", {}).get("amount", 0.0))
                #fixed = float(core.get("otherFeeInfoMap", {}).get("FixedClosingFee", {}).get("total", {}).get("amount", 0.0))
                referral = float(core.get("otherFeeInfoMap", {}).get("ReferralFee", {}).get("total", {}).get("amount", 0.0))
                #variable = float(core.get("otherFeeInfoMap", {}).get("VariableClosingFee", {}).get("total", {}).get("amount", 0.0))
                digital = float(core.get("otherFeeInfoMap", {}).get("DigitalServicesFee", {}).get("total", {}).get("amount", 0.0))

                return round(fulfillment + referral + digital, 2)

            except Exception as e:
                logger.warning(f"Fees retry {attempt} failed {asin}: {e}")
                await asyncio.sleep(1 + attempt * 0.5)

        return None