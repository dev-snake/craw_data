"""
Dual-Mode Crawler Engine
Tự động switch giữa:
- HTML mode (siêu nhanh - aiohttp)
- Browser mode (xử lý JS nặng - Playwright)
"""

import asyncio
from typing import Optional, Dict, List, Tuple
from enum import Enum

from .crawler_async import AsyncCrawler
from .crawler_playwright import PlaywrightCrawler
from .smart_extractor import SmartExtractor


class CrawlMode(Enum):
    """Crawl mode types"""
    HTML = "html"           # Fast HTML-only mode
    BROWSER = "browser"     # Full browser rendering
    AUTO = "auto"           # Auto-switch between modes


class DualModeEngine:
    """
    Intelligent dual-mode crawler engine:
    - Start with fast HTML mode
    - Auto-detect if JS rendering needed
    - Switch to browser mode when necessary
    - Remember mode per domain for efficiency
    """

    def __init__(
        self,
        config: Dict,
        proxy_manager,
        session_cookies: Dict,
        auth_headers: Dict,
        log_func
    ):
        self.config = config
        self.log = log_func
        
        # Initialize both crawlers
        self.html_crawler = AsyncCrawler(
            config, proxy_manager, session_cookies, auth_headers, log_func
        )
        
        self.browser_crawler = None
        if config["crawler"].get("enable_playwright", True):
            self.browser_crawler = PlaywrightCrawler(
                config, proxy_manager, session_cookies, log_func
            )
        
        # Smart extractor
        self.extractor = SmartExtractor()
        
        # Domain mode cache (remember best mode per domain)
        self.domain_modes = {}
        
        # Stats
        self.stats = {
            "html_success": 0,
            "html_failed": 0,
            "browser_success": 0,
            "browser_failed": 0,
            "auto_switches": 0
        }

    # ===================================================================
    # MAIN: Fetch URL with smart mode selection
    # ===================================================================
    async def fetch(
        self, 
        url: str, 
        mode: CrawlMode = CrawlMode.AUTO
    ) -> Tuple[Optional[str], CrawlMode]:
        """
        Fetch URL với smart mode selection
        
        Args:
            url: URL to fetch
            mode: CrawlMode (AUTO, HTML, BROWSER)
        
        Returns:
            (html_content, actual_mode_used)
        """
        domain = self._get_domain(url)
        
        # AUTO mode: Determine best mode
        if mode == CrawlMode.AUTO:
            # Check if we have cached mode for this domain
            if domain in self.domain_modes:
                mode = self.domain_modes[domain]
                await self.log(f"[MODE] Using cached mode for {domain}: {mode.value}")
            else:
                # Start with HTML mode (fastest)
                mode = CrawlMode.HTML
        
        # Try fetching
        html, actual_mode = await self._fetch_with_mode(url, mode)
        
        # If HTML mode failed and browser available, try browser mode
        if not html and mode == CrawlMode.HTML and self.browser_crawler:
            await self.log(f"[AUTO-SWITCH] HTML failed, trying browser mode for {url}")
            html, actual_mode = await self._fetch_with_mode(url, CrawlMode.BROWSER)
            
            if html:
                # Remember to use browser mode for this domain
                self.domain_modes[domain] = CrawlMode.BROWSER
                self.stats["auto_switches"] += 1
                await self.log(f"[MODE] Saved browser mode preference for {domain}")
        
        return html, actual_mode

    async def _fetch_with_mode(
        self, 
        url: str, 
        mode: CrawlMode
    ) -> Tuple[Optional[str], CrawlMode]:
        """
        Fetch URL với specific mode
        """
        if mode == CrawlMode.HTML:
            html = await self.html_crawler.fetch(url)
            if html:
                self.stats["html_success"] += 1
            else:
                self.stats["html_failed"] += 1
            return html, CrawlMode.HTML
        
        elif mode == CrawlMode.BROWSER:
            if not self.browser_crawler:
                await self.log("[ERROR] Browser crawler not initialized")
                return None, mode
            
            html = await self.browser_crawler.fetch_html(url)
            if html:
                self.stats["browser_success"] += 1
            else:
                self.stats["browser_failed"] += 1
            return html, CrawlMode.BROWSER
        
        else:
            # AUTO mode shouldn't reach here
            return None, mode

    # ===================================================================
    # Fetch và extract data (all-in-one)
    # ===================================================================
    async def fetch_and_extract(
        self, 
        url: str, 
        mode: CrawlMode = CrawlMode.AUTO
    ) -> Tuple[List[Dict], Optional[str], CrawlMode]:
        """
        Fetch URL và extract data
        
        Returns:
            (extracted_items, next_page_url, mode_used)
        """
        # 1. Fetch HTML
        html, actual_mode = await self.fetch(url, mode)
        
        if not html:
            return [], None, actual_mode
        
        # 2. Extract data using smart extractor
        items = self.extractor.extract_auto(html, url)
        
        # 3. Auto-detect next page
        next_url = await self._detect_next_page(html, url)
        
        # 4. If no data extracted in HTML mode, try browser mode
        if not items and actual_mode == CrawlMode.HTML and self.browser_crawler:
            await self.log(f"[AUTO-SWITCH] No data in HTML mode, trying browser for {url}")
            html_browser, _ = await self._fetch_with_mode(url, CrawlMode.BROWSER)
            
            if html_browser:
                items = self.extractor.extract_auto(html_browser, url)
                
                if items:
                    # Remember to use browser mode for this domain
                    domain = self._get_domain(url)
                    self.domain_modes[domain] = CrawlMode.BROWSER
                    self.stats["auto_switches"] += 1
                    actual_mode = CrawlMode.BROWSER
                    await self.log(f"[MODE] Browser mode successful, saved preference")
                    
                    # Re-detect next page from browser HTML
                    next_url = await self._detect_next_page(html_browser, url)
        
        return items, next_url, actual_mode

    # ===================================================================
    # Pagination detection
    # ===================================================================
    async def _detect_next_page(self, html: str, base_url: str) -> Optional[str]:
        """
        Auto-detect next page URL
        Uses smart detector
        """
        # Get patterns from extractor's cache
        domain = self._get_domain(base_url)
        patterns = self.extractor.get_patterns(domain)
        
        if not patterns or not patterns.get("pagination"):
            # Need to detect
            patterns = self.extractor.detector.analyze_page(html, base_url)
            self.extractor.set_patterns(domain, patterns)
        
        pagination = patterns.get("pagination")
        if not pagination:
            return None
        
        # Get next URL based on pagination type
        if pagination["type"] == "button":
            return pagination.get("next_url")
        
        elif pagination["type"] == "links":
            # For page numbers, need to construct next URL
            current = pagination.get("current", 1)
            pattern = pagination.get("pattern", "")
            if pattern and "{page}" in pattern:
                next_page = current + 1
                return pattern.replace("{page}", str(next_page))
        
        return None

    # ===================================================================
    # Batch fetch (concurrent)
    # ===================================================================
    async def fetch_batch(
        self, 
        urls: List[str], 
        mode: CrawlMode = CrawlMode.AUTO,
        max_concurrent: int = None
    ) -> List[Tuple[str, Optional[str], CrawlMode]]:
        """
        Fetch multiple URLs concurrently
        
        Returns:
            List of (url, html, mode_used)
        """
        if max_concurrent is None:
            max_concurrent = self.config["crawler"].get("max_concurrency", 5)
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_one(url):
            async with semaphore:
                html, actual_mode = await self.fetch(url, mode)
                return (url, html, actual_mode)
        
        tasks = [fetch_one(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                await self.log(f"[ERROR] Batch fetch error: {result}")
                continue
            valid_results.append(result)
        
        return valid_results

    # ===================================================================
    # Mode management
    # ===================================================================
    def set_domain_mode(self, domain: str, mode: CrawlMode):
        """Manually set preferred mode for domain"""
        self.domain_modes[domain] = mode

    def get_domain_mode(self, domain: str) -> Optional[CrawlMode]:
        """Get preferred mode for domain"""
        return self.domain_modes.get(domain)

    def clear_domain_modes(self):
        """Clear domain mode cache"""
        self.domain_modes.clear()

    # ===================================================================
    # Stats & monitoring
    # ===================================================================
    def get_stats(self) -> Dict:
        """Get crawling statistics"""
        total_html = self.stats["html_success"] + self.stats["html_failed"]
        total_browser = self.stats["browser_success"] + self.stats["browser_failed"]
        
        return {
            **self.stats,
            "html_success_rate": (
                self.stats["html_success"] / total_html if total_html > 0 else 0
            ),
            "browser_success_rate": (
                self.stats["browser_success"] / total_browser if total_browser > 0 else 0
            ),
            "total_requests": total_html + total_browser
        }

    async def log_stats(self):
        """Log current statistics"""
        stats = self.get_stats()
        
        await self.log("=" * 50)
        await self.log("[STATS] Dual-Mode Engine Statistics")
        await self.log(f"  HTML: {stats['html_success']}/{stats['html_success'] + stats['html_failed']} "
                      f"({stats['html_success_rate']:.1%} success)")
        await self.log(f"  Browser: {stats['browser_success']}/{stats['browser_success'] + stats['browser_failed']} "
                      f"({stats['browser_success_rate']:.1%} success)")
        await self.log(f"  Auto-switches: {stats['auto_switches']}")
        await self.log(f"  Total requests: {stats['total_requests']}")
        await self.log(f"  Cached domain modes: {len(self.domain_modes)}")
        await self.log("=" * 50)

    # ===================================================================
    # Utilities
    # ===================================================================
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or parsed.path

    # ===================================================================
    # Infinite scroll support
    # ===================================================================
    async def fetch_infinite_scroll(
        self, 
        url: str, 
        max_scrolls: int = 10
    ) -> List[Dict]:
        """
        Fetch page với infinite scroll support
        Requires browser mode
        """
        if not self.browser_crawler:
            await self.log("[ERROR] Browser crawler required for infinite scroll")
            return []
        
        await self.log(f"[INFINITE] Fetching {url} with up to {max_scrolls} scrolls")
        
        # TODO: Implement infinite scroll với Playwright
        # This requires extending PlaywrightCrawler with scroll support
        
        await self.log("[WARN] Infinite scroll not yet implemented")
        
        # Fallback to regular fetch
        items, _, _ = await self.fetch_and_extract(url, CrawlMode.BROWSER)
        return items


# ===================================================================
# USAGE EXAMPLE
# ===================================================================
if __name__ == "__main__":
    import json
    
    # Mock config
    config = {
        "crawler": {
            "max_concurrency": 5,
            "request_timeout": 30,
            "retry": 3,
            "delay_range": [1, 2],
            "enable_playwright": True
        },
        "selectors": {
            "data_selector": ".product",
            "title_selector": "h3",
            "content_attribute": "text"
        },
        "pagination": {
            "selector": "a.next",
            "attribute": "href"
        }
    }
    
    # Mock log function
    async def log(msg):
        print(msg)
    
    # Test
    async def test():
        engine = DualModeEngine(config, None, {}, {}, log)
        
        # Test fetch
        html, mode = await engine.fetch("https://example.com", CrawlMode.AUTO)
        print(f"Fetched with mode: {mode}")
        
        # Test stats
        await engine.log_stats()
    
    # Run test
    # asyncio.run(test())
