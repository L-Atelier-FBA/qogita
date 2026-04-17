import asyncio
import aiohttp
from core.database import Database
from core.logger import get_logger
from core.sas_scraper import SAScraper
from core.seller_central import SellerCentral
from core.ean2asin import convert
import json

JSON_URL = "https://raw.githubusercontent.com/L-Atelier-FBA/qogita_bs/refs/heads/main/products.json"
COOKIE_URL = "https://raw.githubusercontent.com/L-Atelier-FBA/cookie_refresh/refs/heads/main/cookies.json"

logger = get_logger("Scanner")


async def fetch_products(session):
    logger.info("Fetching products JSON...")
    try:
        async with session.get(JSON_URL, timeout=60) as response:
            logger.info(f"Products response status: {response.status}")

            if response.status != 200:
                logger.warning("Failed to fetch products JSON")
                return []

            data = await response.text()
            products = json.loads(data)

            logger.info(f"Fetched {len(products)} products from source")
            return products

    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        return []


async def fetch_cookies(session):
    logger.info("Fetching cookies JSON...")
    try:
        async with session.get(COOKIE_URL, timeout=60) as response:
            logger.info(f"Cookies response status: {response.status}")

            if response.status != 200:
                logger.warning("Failed to fetch cookies")
                return None

            cookie = json.loads(await response.text())

            result = {
                "amazon": cookie.get("amazon1"),
                "seller": cookie.get("amazon2"),
                "sas": cookie.get("sas")
            }

            logger.info("Cookies successfully loaded")
            return result

    except Exception as e:
        logger.error(f"Cookie fetch error: {e}")
        return None


async def process_product(product, semaphore, db, amz_cookie, sc, sas):
    async with semaphore:
        ean = product.get("product_gtin")
        asin = await convert(ean, amz_cookie)

        logger.info(f"Processing product ASIN={asin} EAN={ean}")

        try:
            if not asin or not ean:
                logger.warning("Missing ASIN or EAN, skipping product")
                return

            supplier_price = float(product.get("supplier_price", 0))
            supplier_cost = supplier_price * 1.2

            logger.info(f"{asin} supplier_price={supplier_price} supplier_cost={supplier_cost}")

            title, link, gl, img = await sc.get_product_data(asin)

            if not gl:
                logger.warning(f"{asin} missing GL, skipping")
                return

            price = await sc.get_price(asin)

            if price is None or price <= 0:
                logger.warning(f"{asin} invalid price: {price}")
                return

            logger.info(f"{asin} price={price}")

            fees = await sc.get_fees(asin, gl, price)

            if fees is None:
                logger.warning(f"{asin} fees returned None")
                return

            logger.info(f"{asin} fees={fees}")

            vat_on_fees = fees * (20 / 100)

            profit = price - fees - supplier_cost - vat_on_fees

            if supplier_cost <= 0:
                logger.warning(f"{asin} invalid supplier cost")
                return

            roi = (profit / supplier_cost) * 100

            logger.info(f"{asin} profit={profit:.2f} roi={roi:.2f}")

            if roi < 25:
                logger.info(f"{asin} rejected: ROI < 25 ({roi:.2f})")
                return

            if profit < 1:
                logger.info(f"{asin} rejected: profit < 1 ({profit:.2f})")
                return

            sales = await sas.get_data(asin)

            logger.info(f"{asin} sales raw={sales}")

            try:
                sales = int(sales or 0)
            except Exception as e:
                logger.warning(f"{asin} invalid sales format: {sales} ({e})")
                return

            if sales < 5:
                logger.info(f"{asin} rejected: sales < 5 ({sales})")
                return

            deal = {
                "ean": ean,
                "asin": asin,
                "name": product.get("product_name", ""),
                "supplier_cost": supplier_cost,
                "amazon_price": price,
                "fees": fees,
                "profit": profit,
                "roi": roi,
                "estimated_sales": sales,
                "amazon_link": f"https://www.amazon.fr/dp/{asin}",
                "supplier_link": product.get("product_link"),
                "sas_link": f"https://sas.selleramp.com/sas/lookup?SasLookup%5Bsearch_term%5D={asin}",
                "image_url": img
            }

            saved = await db.save_deal(deal)

            if saved:
                logger.info(f"DEAL SAVED → ASIN={asin} ROI={roi:.2f}% Profit={profit:.2f}")
            else:
                logger.info(f"Duplicate skipped → ASIN={asin}")

        except Exception as e:
            logger.error(f"Fatal error processing {asin}: {e}")


async def main():
    logger.info("FBA Scanner STARTED...")

    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(limit=100, ssl=False)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:

        products, cookie = await asyncio.gather(
            fetch_products(session),
            fetch_cookies(session)
        )

        if not products:
            logger.error("No products loaded, exiting")
            return

        if not cookie:
            logger.error("No cookies loaded, exiting")
            return

        logger.info(f"Products loaded: {len(products)}")

        db = Database()
        await db.reset_db()
        logger.warning("Database reset (intentional)")

        seen = set()
        unique_products = []

        for p in products:
            ean = p.get("product_gtin")
            if ean and ean not in seen:
                seen.add(ean)
                unique_products.append(p)

        logger.info(f"Unique products: {len(unique_products)}")

        sas = SAScraper(cookies=cookie["sas"], headless=True, max_pages=10)
        sc = SellerCentral(cookie=cookie["seller"])

        await sas.start()
        logger.info("SAS scraper started")

        semaphore = asyncio.Semaphore(20)

        tasks = [
            process_product(p, semaphore, db, cookie["amazon"], sc, sas)
            for p in unique_products
        ]

        logger.info("Launching product processing tasks...")
        await asyncio.gather(*tasks)

        await sas.close()
        logger.info("SAS scraper closed")

    logger.info("FBA Scanner FINISHED...")


if __name__ == "__main__":
    asyncio.run(main())
