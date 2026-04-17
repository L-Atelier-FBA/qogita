from bs4 import BeautifulSoup
from .requester import Requester
from .logger import get_logger

logger = get_logger("ean2asin")


async def convert(ean: str, cookie: str):
    url = f"https://www.amazon.fr/s?k={ean}"
    referrer = "https://www.amazon.fr/"

    try:
        async with Requester(url=url, referrer=referrer, cookie=cookie) as scraper:
            response = await scraper.fetch_get()

            if not response or response.status_code != 200:
                logger.warning(f"{ean} - Blocked or request failed.")
                return None

            html = response.content.decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "lxml")

            products = soup.find_all("div", attrs={"data-component-type": "s-search-result"})

            for product in products:
                asin = product.get("data-asin")
                if not asin or len(asin) != 10:
                    continue

                sponsored = product.find("span")
                if sponsored and "Sponsored" in sponsored.get_text():
                    continue

                return asin

    except Exception as e:
        logger.warning(e)
        return None

    return None