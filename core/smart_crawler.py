"""
Smart Crawler - Main Integration
Tích hợp tất cả smart modules vào một crawler thông minh
"""

import asyncio
from typing import Dict, List, Optional, Callable

from .dual_mode_engine import DualModeEngine, CrawlMode
from .scale_handler import ScaleHandler
from .smart_extractor import SmartExtractor
from .smart_detector import SmartDetector
from .proxy_manager import ProxyManager
from .login import LoginManager
from .exporter import Exporter


class SmartCrawler:
    """
    Smart Crawler - Zero configuration crawler
    
    Features:
    - Auto-detect selectors, pagination, infinite scroll
    - Dual-mode engine (HTML/Browser with auto-switch)
    - Smart data extraction
    - Scale to 10k-100k pages
    - Multi-domain support
    - Progress tracking & resume
    """

    def __init__(self, config: Dict, log_func: Callable):
        self.config = config
        self.log = log_func
        
        # Components (initialized on demand)
        self.proxy_manager = None
        self.login_manager = None
        self.engine = None
        self.scale_handler = None
        self.exporter = None
        
        # Session state
        self.session_cookies = {}
        self.auth_headers = {}

    # ===================================================================
    # Initialize components
    # ===================================================================
    async def initialize(self):
        """Initialize all components"""
        await self.log("[SMART] Initializing Smart Crawler...")
        
        # Proxy manager
        self.proxy_manager = ProxyManager(self.config.get("proxy", {}))
        
        # Login manager
        self.login_manager = LoginManager(
            self.config.get("login", {}),
            self.proxy_manager
        )
        
        # Perform login if configured
        self.session_cookies, self.auth_headers = await self.login_manager.perform_login(
            self.log
        )
        
        # Dual-mode engine
        self.engine = DualModeEngine(
            self.config,
            self.proxy_manager,
            self.session_cookies,
            self.auth_headers,
            self.log
        )
        
        # Scale handler
        self.scale_handler = ScaleHandler(
            self.engine,
            self.config,
            self.log
        )
        
        # Exporter
        self.exporter = Exporter(self.config)
        
        await self.log("[SMART] Initialization complete!")

    # ===================================================================
    # SMART MODE: Single URL with auto-detection
    # ===================================================================
    async def crawl_smart(
        self,
        url: str,
        max_pages: int = 100,
        mode: str = "auto"
    ) -> Dict:
        """
        Smart crawl single URL:
        - Auto-detect everything
        - No configuration needed
        - Handle pagination automatically
        
        Args:
            url: Starting URL
            max_pages: Max pages to crawl
            mode: "auto", "html", or "browser"
        
        Returns:
            Summary statistics
        """
        await self.initialize()
        
        await self.log("=" * 60)
        await self.log("[SMART MODE] Starting smart crawl")
        await self.log(f"  URL: {url}")
        await self.log(f"  Max pages: {max_pages}")
        await self.log(f"  Mode: {mode}")
        await self.log("=" * 60)
        
        # Parse mode
        crawl_mode = self._parse_mode(mode)
        
        # Result callback
        async def result_callback(item):
            self.exporter.add_result(item)
            await self.log(f"[DATA] {item.get('title', 'N/A')}")
        
        # Progress callback
        async def progress_callback(progress):
            if progress["pages_crawled"] % 10 == 0:
                await self.log(
                    f"[PROGRESS] {progress['pages_crawled']}/{progress['pages_total']} "
                    f"({progress['progress_pct']:.1f}%) - "
                    f"Items: {progress['items_extracted']}"
                )
        
        # Set callbacks
        self.scale_handler.progress_callback = progress_callback
        
        # Start crawl
        summary = await self.scale_handler.crawl(
            start_urls=[url],
            mode=crawl_mode,
            max_pages=max_pages,
            result_callback=result_callback
        )
        
        # Export results
        await self.log("[EXPORT] Saving results...")
        self.exporter.export_all()
        
        await self.log("[SMART MODE] Complete!")
        
        return summary

    # ===================================================================
    # MULTI-DOMAIN MODE: Crawl nhiều domains
    # ===================================================================
    async def crawl_multi_domain(
        self,
        urls: List[str],
        max_pages_per_domain: int = 1000,
        mode: str = "auto"
    ) -> Dict:
        """
        Multi-domain crawl:
        - Crawl multiple domains in parallel
        - Balance load across domains
        - Auto-detect for each domain
        
        Args:
            urls: List of starting URLs
            max_pages_per_domain: Max pages per domain
            mode: "auto", "html", or "browser"
        
        Returns:
            Summary statistics
        """
        await self.initialize()
        
        await self.log("=" * 60)
        await self.log("[MULTI-DOMAIN MODE] Starting multi-domain crawl")
        await self.log(f"  Domains: {len(set(self._get_domain(u) for u in urls))}")
        await self.log(f"  Max pages per domain: {max_pages_per_domain}")
        await self.log(f"  Mode: {mode}")
        await self.log("=" * 60)
        
        # Parse mode
        crawl_mode = self._parse_mode(mode)
        
        # Result callback
        async def result_callback(item):
            self.exporter.add_result(item)
        
        # Progress callback
        async def progress_callback(progress):
            if progress["pages_crawled"] % 20 == 0:
                await self.log(
                    f"[PROGRESS] {progress['pages_crawled']} pages - "
                    f"{progress['items_extracted']} items"
                )
        
        # Set callbacks
        self.scale_handler.progress_callback = progress_callback
        
        # Start crawl
        summary = await self.scale_handler.crawl_multi_domain(
            start_urls=urls,
            mode=crawl_mode,
            max_pages_per_domain=max_pages_per_domain,
            result_callback=result_callback
        )
        
        # Export results
        await self.log("[EXPORT] Saving results...")
        self.exporter.export_all()
        
        await self.log("[MULTI-DOMAIN MODE] Complete!")
        
        return summary

    # ===================================================================
    # QUICK TEST MODE: Test single page
    # ===================================================================
    async def test_page(self, url: str, mode: str = "auto") -> Dict:
        """
        Quick test single page:
        - Detect patterns
        - Extract data
        - Show what will be crawled
        
        Returns:
            Test results with detected patterns and sample data
        """
        await self.initialize()
        
        await self.log("=" * 60)
        await self.log("[TEST MODE] Testing page")
        await self.log(f"  URL: {url}")
        await self.log("=" * 60)
        
        # Parse mode
        crawl_mode = self._parse_mode(mode)
        
        # Fetch and extract
        items, next_url, actual_mode = await self.engine.fetch_and_extract(
            url, crawl_mode
        )
        
        # Get detected patterns
        domain = self._get_domain(url)
        patterns = self.engine.extractor.get_patterns(domain)
        
        # Results
        result = {
            "url": url,
            "mode_used": actual_mode.value,
            "items_found": len(items),
            "sample_items": items[:5],  # First 5 items
            "next_page": next_url,
            "patterns": patterns
        }
        
        # Log results
        await self.log(f"\n[TEST RESULTS]")
        await self.log(f"  Mode used: {actual_mode.value}")
        await self.log(f"  Items found: {len(items)}")
        await self.log(f"  Next page: {next_url}")
        
        if patterns and patterns.get("data_containers"):
            best = patterns["data_containers"][0]
            await self.log(f"\n[DETECTED PATTERN]")
            await self.log(f"  Selector: {best['selector']}")
            await self.log(f"  Count: {best['count']}")
            await self.log(f"  Sample: {best['sample']}")
        
        if patterns and patterns.get("pagination"):
            await self.log(f"\n[PAGINATION]")
            await self.log(f"  Type: {patterns['pagination']['type']}")
        
        if items:
            await self.log(f"\n[SAMPLE ITEMS]")
            for i, item in enumerate(items[:3], 1):
                await self.log(f"  Item {i}:")
                await self.log(f"    Title: {item.get('title', 'N/A')}")
                await self.log(f"    Price: {item.get('price', 'N/A')}")
                await self.log(f"    Link: {item.get('link', 'N/A')}")
        
        await self.log("=" * 60)
        
        return result

    # ===================================================================
    # Control methods
    # ===================================================================
    def stop(self):
        """Stop crawling"""
        if self.scale_handler:
            self.scale_handler.stop()

    def pause(self):
        """Pause crawling"""
        if self.scale_handler:
            self.scale_handler.pause()

    def resume(self):
        """Resume crawling"""
        if self.scale_handler:
            self.scale_handler.resume()

    # ===================================================================
    # Statistics
    # ===================================================================
    async def get_stats(self) -> Dict:
        """Get current statistics"""
        stats = {}
        
        if self.engine:
            stats["engine"] = self.engine.get_stats()
        
        if self.scale_handler and self.scale_handler.session:
            stats["session"] = {
                "pages_crawled": self.scale_handler.session.pages_crawled,
                "items_extracted": self.scale_handler.session.items_extracted,
                "errors": self.scale_handler.session.errors,
                "domains": len(self.scale_handler.session.domains)
            }
        
        if self.exporter:
            stats["results"] = {
                "total_items": len(self.exporter.results)
            }
        
        return stats

    # ===================================================================
    # Utilities
    # ===================================================================
    def _parse_mode(self, mode: str) -> CrawlMode:
        """Parse mode string to CrawlMode enum"""
        mode = mode.lower()
        if mode == "html":
            return CrawlMode.HTML
        elif mode == "browser":
            return CrawlMode.BROWSER
        else:
            return CrawlMode.AUTO

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or parsed.path


# ===================================================================
# USAGE EXAMPLE
# ===================================================================
if __name__ == "__main__":
    # Example config
    config = {
        "crawler": {
            "max_concurrency": 10,
            "request_timeout": 30,
            "retry": 3,
            "delay_range": [0.5, 1.5],
            "enable_playwright": True,
            "follow_robots": True,
            "domain_delay": 1.0
        },
        "export": {
            "output_directory": "output",
            "formats": ["json", "csv"]
        },
        "max_pages": 100000,
        "max_depth": 10,
        "checkpoint_interval": 100
    }
    
    async def log(msg):
        print(msg)
    
    async def test():
        crawler = SmartCrawler(config, log)
        
        # Test mode
        result = await crawler.test_page("https://example.com/products")
        print(f"\nTest result: {result}")
    
    # asyncio.run(test())
