import aiohttp
import asyncio
import random

from .parser import Parser
from .utils import log_time, same_domain


class AsyncCrawler:
    def __init__(self, config, proxy_manager, session_cookies, auth_headers, log_func):
        self.config = config
        self.proxy_manager = proxy_manager
        self.session_cookies = session_cookies or {}
        self.auth_headers = auth_headers or {}
        self.log = log_func

        self.max_concurrency = config["crawler"]["max_concurrency"]
        self.request_timeout = config["crawler"]["request_timeout"]
        self.retry = config["crawler"]["retry"]
        self.delay_min, self.delay_max = config["crawler"]["delay_range"]

        self.parser = Parser(config)

        self.sem = asyncio.Semaphore(self.max_concurrency)

    # ======================================================
    # Fetch HTML with retries, delay, proxy, cookies
    # ======================================================
    async def fetch(self, url):
        async with self.sem:
            for attempt in range(1, self.retry + 1):
                try:
                    proxy = await self.proxy_manager.get_aiohttp_proxy()

                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                    }
                    headers.update(self.auth_headers)

                    timeout = aiohttp.ClientTimeout(total=self.request_timeout)

                    async with aiohttp.ClientSession(cookies=self.session_cookies) as session:
                        async with session.get(
                            url,
                            headers=headers,
                            proxy=proxy,
                            timeout=timeout,
                        ) as resp:

                            if resp.status == 200:
                                html = await resp.text()
                                await self.log(log_time(f"[FETCH] OK 200 -> {url}"))
                                await self.random_delay()
                                return html

                            await self.log(log_time(f"[FETCH] Status {resp.status} -> {url}"))

                except asyncio.TimeoutError:
                    await self.log(log_time(f"[TIMEOUT] {url}"))

                except Exception as e:
                    await self.log(log_time(f"[ERROR] {url} -> {e}"))

                # Retry delay
                await self.random_delay()

            return None

    # ======================================================
    # Extract data from HTML
    # ======================================================
    async def extract_data(self, html):
        return self.parser.extract_data(html)

    # ======================================================
    # Get next page URL for pagination
    # ======================================================
    async def get_next_page(self, html, base_url):
        return self.parser.get_next_page(html, base_url)

    # ======================================================
    # Random delay between requests
    # ======================================================
    async def random_delay(self):
        d = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(d)
