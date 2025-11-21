import asyncio
from playwright.async_api import async_playwright

from .utils import log_time


class PlaywrightCrawler:
    def __init__(self, config, proxy_manager, session_cookies, log_func):
        self.config = config
        self.proxy_manager = proxy_manager
        self.session_cookies = session_cookies
        self.log = log_func
        self.timeout = config["crawler"]["request_timeout"] * 1000  # ms

    # ======================================================
    # Render page and return HTML
    # ======================================================
    async def fetch_html(self, url):
        await self.log(log_time(f"[PW] Starting browser for {url}"))

        proxy_cfg = await self.proxy_manager.get_playwright_proxy()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )

                context_kwargs = {}

                # Proxy support
                if proxy_cfg:
                    context_kwargs["proxy"] = proxy_cfg

                # Create browser context
                context = await browser.new_context(**context_kwargs)

                # Cookie login support
                if self.session_cookies:
                    cookies = [
                        {"name": k, "value": v, "url": url}
                        for k, v in self.session_cookies.items()
                    ]
                    await context.add_cookies(cookies)

                page = await context.new_page()

                try:
                    await page.goto(url, timeout=self.timeout, wait_until="networkidle")
                    html = await page.content()
                    await self.log(log_time(f"[PW] Rendered -> {url}"))

                except Exception as e:
                    await self.log(log_time(f"[PW][ERROR] {url} -> {e}"))
                    html = None

                await context.close()
                await browser.close()

                return html

        except Exception as e:
            await self.log(log_time(f"[PW][CRASH] {e}"))
            return None
