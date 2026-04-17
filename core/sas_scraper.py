import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from .logger import get_logger

logger = get_logger("SAScraper")


class SAScraper:
    def __init__(
        self,
        cookies: list | None,
        max_pages: int = 10,
        headless: bool = True
    ):
        self.cookies = cookies
        self.base_url = "https://sas.selleramp.com/sas/lookup?src=web&SasLookup%5Bsearch_term%5D={}"
        self.max_pages = max_pages
        self.headless = headless

        self.playwright = None
        self.browser = None
        self.context = None
        self.semaphore = asyncio.Semaphore(max_pages)

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context()
        if self.cookies:
            await self.context.add_cookies(self.cookies)
        logger.info("SAS scraper started.")

    async def close(self):
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(e)
        logger.info("SAS scraper closed.")

    async def get_data(self, asin: str):
        async with self.semaphore:
            try:
                page = await self.context.new_page()
                await page.goto(self.base_url.format(asin), wait_until="domcontentloaded")

                html = await page.content()

                if "No results were found" in html:
                    return None

                soup = BeautifulSoup(html, "lxml")

                tag = soup.find("span", class_="estimated_sales_per_mo")

                if not tag:
                    return None

                sales = tag.get_text(strip=True).replace("+", "").replace("/mo", "").replace(",", "").strip()

                if not sales or sales == "Unknown":
                    return None

                return int(sales)

            except Exception as e:
                logger.warning(f"SAS failed {asin}: {e}")
                return None

            finally:
                if page:
                    await page.close()