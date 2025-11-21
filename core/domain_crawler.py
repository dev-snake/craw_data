import asyncio
from .parser import Parser
from .utils import (
    log_time,
    same_domain,
    is_allowed_extension,
    normalize_url
)


class DomainCrawler:
    def __init__(self, config, queue, robots_checker, async_crawler, playwright_crawler, log_func):
        self.config = config
        self.queue = queue
        self.robots = robots_checker
        self.async_crawler = async_crawler
        self.playwright = playwright_crawler
        self.log = log_func
        self.parser = Parser(config)

        self.max_pages = config["domain_crawler"]["max_pages"]
        self.same_domain_only = config["domain_crawler"]["same_domain_only"]
        self.max_depth = config["crawler"]["max_depth"]
        self.banned_exts = config["domain_crawler"]["exclude_extensions"]

        self.start_domain = None
        self.page_count = 0

    # ==========================================================
    # Main entry for domain crawl
    # ==========================================================
    async def run(self, start_url, running, result_signal, result_callback=None):
        """
        Crawl across the domain breadth-first until limits are reached.

        running: callable or bool used to check the stop flag.
        result_signal: Qt signal to push data to the UI.
        result_callback: optional callable to persist each item (e.g., exporter).
        """
        self.start_domain = start_url.split("/")[2]

        await self.log(log_time(f"[DOMAIN] Started crawling domain: {self.start_domain}"))

        self.queue.add(start_url)

        running_fn = running if callable(running) else (lambda: bool(running))

        while self.queue.has_next() and running_fn():
            if self.page_count >= self.max_pages:
                await self.log(log_time("[DOMAIN] Reached max page limit"))
                break

            url = self.queue.pop()

            if not await self.robots.allowed(url):
                await self.log(log_time(f"[robots.txt] Blocked -> {url}"))
                continue

            # Check domain restriction
            if self.same_domain_only and not same_domain(url, start_url):
                continue

            # Skip non-HTML files
            if not is_allowed_extension(url, self.banned_exts):
                continue

            html = None

            # Try Playwright first if enabled
            if self.config["crawler"]["enable_playwright"] and self.playwright:
                html = await self.playwright.fetch_html(url)

            # Fallback to async crawler
            if not html:
                html = await self.async_crawler.fetch(url)

            if not html:
                await self.log(log_time(f"[DOMAIN] Failed -> {url}"))
                continue

            self.page_count += 1
            await self.log(log_time(f"[DOMAIN] Crawled ({self.page_count}) -> {url}"))

            # ===== Extract data =====
            data = self.parser.extract_data(html)
            for item in data:
                result_signal.emit(item)
                if result_callback:
                    result_callback(item)

            # ===== Extract new links =====
            if self.page_count <= self.max_depth:
                links = self.parser.extract_links(html, url)
                for link in links:
                    if is_allowed_extension(link, self.banned_exts):
                        self.queue.add(link)

        await self.log(log_time("[DOMAIN] Crawl complete."))
