"""
Scale Handler Module
Xử lý crawling quy mô lớn:
- 10,000 - 100,000+ pages
- Multi-domain crawling
- Progress tracking & resume
- Rate limiting & politeness
- Error recovery
- Memory optimization
"""

import asyncio
import time
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
from urllib.parse import urlparse

from .dual_mode_engine import DualModeEngine, CrawlMode
from .queue_manager import CrawlQueue
from .robots_checker import RobotsChecker


@dataclass
class CrawlSession:
    """Crawl session state"""
    session_id: str
    start_time: float
    domains: Set[str] = field(default_factory=set)
    pages_crawled: int = 0
    pages_total: int = 0
    items_extracted: int = 0
    errors: int = 0
    current_status: str = "running"
    last_checkpoint: float = 0


class ScaleHandler:
    """
    Handle large-scale crawling:
    - Efficient queue management
    - Progress tracking
    - Checkpoint & resume
    - Rate limiting per domain
    - Memory-efficient processing
    """

    def __init__(
        self,
        engine: DualModeEngine,
        config: Dict,
        log_func: Callable,
        progress_callback: Optional[Callable] = None
    ):
        self.engine = engine
        self.config = config
        self.log = log_func
        self.progress_callback = progress_callback
        
        # Queue management
        self.queue = CrawlQueue()
        self.visited = set()
        
        # Robots.txt checker
        self.robots = RobotsChecker(
            follow=config["crawler"].get("follow_robots", True)
        )
        
        # Domain rate limiting
        self.domain_delays = {}  # domain -> last_request_time
        self.domain_delay = config["crawler"].get("domain_delay", 1.0)
        
        # Session tracking
        self.session: Optional[CrawlSession] = None
        
        # Checkpoint settings
        self.checkpoint_interval = config.get("checkpoint_interval", 100)  # pages
        self.checkpoint_callback: Optional[Callable] = None
        
        # Limits
        self.max_pages = config.get("max_pages", 100000)
        self.max_depth = config.get("max_depth", 10)
        self.max_domains = config.get("max_domains", 100)
        
        # Controls
        self.running = True

    # ===================================================================
    # MAIN: Start large-scale crawl
    # ===================================================================
    async def crawl(
        self,
        start_urls: List[str],
        mode: CrawlMode = CrawlMode.AUTO,
        max_pages: Optional[int] = None,
        result_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Start large-scale crawl
        
        Args:
            start_urls: List of starting URLs
            mode: Crawl mode (AUTO, HTML, BROWSER)
            max_pages: Max pages to crawl (override config)
            result_callback: Callback for each extracted item
        
        Returns:
            Crawl summary statistics
        """
        # Initialize session
        self.session = CrawlSession(
            session_id=self._generate_session_id(),
            start_time=time.time(),
            pages_total=max_pages or self.max_pages
        )
        
        await self.log(f"[SCALE] Starting crawl session: {self.session.session_id}")
        await self.log(f"[SCALE] Target: {self.session.pages_total} pages")
        await self.log(f"[SCALE] Mode: {mode.value}")
        
        # Add start URLs to queue
        for url in start_urls:
            self.queue.add(url)
            domain = self._get_domain(url)
            self.session.domains.add(domain)
        
        # Main crawl loop
        while self.running and self.queue.has_next():
            # Check limits
            if self.session.pages_crawled >= self.session.pages_total:
                await self.log(f"[SCALE] Reached page limit: {self.session.pages_total}")
                break
            
            if len(self.session.domains) > self.max_domains:
                await self.log(f"[SCALE] Reached domain limit: {self.max_domains}")
                break
            
            # Get next URL
            url = self.queue.pop()
            
            # Skip if already visited
            if url in self.visited:
                continue
            
            # Check depth
            depth = self.queue.get_depth(url)
            if depth > self.max_depth:
                continue
            
            # Check robots.txt
            if not await self.robots.allowed(url):
                await self.log(f"[ROBOTS] Blocked: {url}")
                continue
            
            # Rate limiting per domain
            await self._apply_rate_limit(url)
            
            # Crawl page
            try:
                items, next_url, actual_mode = await self.engine.fetch_and_extract(
                    url, mode
                )
                
                # Mark as visited
                self.visited.add(url)
                self.session.pages_crawled += 1
                
                # Handle results
                if items:
                    self.session.items_extracted += len(items)
                    
                    # Call result callback for each item
                    if result_callback:
                        for item in items:
                            await result_callback(item)
                
                # Add next page to queue (pagination)
                if next_url and next_url not in self.visited:
                    self.queue.add(next_url, parent=url)
                
                # Progress update
                await self._update_progress()
                
                # Checkpoint
                if self.session.pages_crawled % self.checkpoint_interval == 0:
                    await self._checkpoint()
                
            except Exception as e:
                await self.log(f"[ERROR] Failed to crawl {url}: {e}")
                self.session.errors += 1
        
        # Final checkpoint
        await self._checkpoint()
        
        # Summary
        summary = await self._generate_summary()
        await self._log_summary(summary)
        
        return summary

    # ===================================================================
    # Multi-domain crawling
    # ===================================================================
    async def crawl_multi_domain(
        self,
        start_urls: List[str],
        mode: CrawlMode = CrawlMode.AUTO,
        max_pages_per_domain: int = 1000,
        result_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Crawl multiple domains with balanced distribution
        
        Args:
            start_urls: List of starting URLs (can be from different domains)
            mode: Crawl mode
            max_pages_per_domain: Max pages per domain
            result_callback: Callback for results
        
        Returns:
            Summary statistics
        """
        await self.log(f"[MULTI-DOMAIN] Starting multi-domain crawl")
        await self.log(f"[MULTI-DOMAIN] Domains: {len(set(self._get_domain(u) for u in start_urls))}")
        await self.log(f"[MULTI-DOMAIN] Max pages per domain: {max_pages_per_domain}")
        
        # Track pages per domain
        domain_counts = {}
        
        # Initialize session
        self.session = CrawlSession(
            session_id=self._generate_session_id(),
            start_time=time.time(),
            pages_total=len(start_urls) * max_pages_per_domain
        )
        
        # Add start URLs
        for url in start_urls:
            self.queue.add(url)
            domain = self._get_domain(url)
            self.session.domains.add(domain)
            domain_counts[domain] = 0
        
        # Crawl loop with domain balancing
        while self.running and self.queue.has_next():
            url = self.queue.pop()
            
            # Skip if visited
            if url in self.visited:
                continue
            
            # Check domain limit
            domain = self._get_domain(url)
            if domain_counts.get(domain, 0) >= max_pages_per_domain:
                continue
            
            # Check robots.txt
            if not await self.robots.allowed(url):
                continue
            
            # Rate limiting
            await self._apply_rate_limit(url)
            
            # Crawl
            try:
                items, next_url, actual_mode = await self.engine.fetch_and_extract(
                    url, mode
                )
                
                # Update counts
                self.visited.add(url)
                self.session.pages_crawled += 1
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                
                # Handle results
                if items:
                    self.session.items_extracted += len(items)
                    if result_callback:
                        for item in items:
                            await result_callback(item)
                
                # Add next page
                if next_url and next_url not in self.visited:
                    next_domain = self._get_domain(next_url)
                    if domain_counts.get(next_domain, 0) < max_pages_per_domain:
                        self.queue.add(next_url, parent=url)
                
                # Progress
                await self._update_progress()
                
                # Checkpoint
                if self.session.pages_crawled % self.checkpoint_interval == 0:
                    await self._checkpoint()
                    await self.log(f"[MULTI-DOMAIN] Progress: {domain_counts}")
                
            except Exception as e:
                await self.log(f"[ERROR] Failed: {url} - {e}")
                self.session.errors += 1
        
        # Summary
        await self.log(f"[MULTI-DOMAIN] Final counts per domain:")
        for domain, count in domain_counts.items():
            await self.log(f"  {domain}: {count} pages")
        
        summary = await self._generate_summary()
        summary["domain_counts"] = domain_counts
        await self._log_summary(summary)
        
        return summary

    # ===================================================================
    # Rate limiting
    # ===================================================================
    async def _apply_rate_limit(self, url: str):
        """
        Apply rate limiting per domain
        """
        domain = self._get_domain(url)
        
        # Check last request time for this domain
        last_time = self.domain_delays.get(domain, 0)
        now = time.time()
        elapsed = now - last_time
        
        # Wait if needed
        if elapsed < self.domain_delay:
            wait_time = self.domain_delay - elapsed
            await asyncio.sleep(wait_time)
        
        # Update last request time
        self.domain_delays[domain] = time.time()

    # ===================================================================
    # Progress tracking
    # ===================================================================
    async def _update_progress(self):
        """Update and report progress"""
        if not self.session:
            return
        
        # Calculate progress
        progress_pct = (
            self.session.pages_crawled / self.session.pages_total * 100
            if self.session.pages_total > 0 else 0
        )
        
        elapsed = time.time() - self.session.start_time
        pages_per_sec = self.session.pages_crawled / elapsed if elapsed > 0 else 0
        
        # Estimate time remaining
        remaining_pages = self.session.pages_total - self.session.pages_crawled
        eta_seconds = remaining_pages / pages_per_sec if pages_per_sec > 0 else 0
        
        # Log progress every 10 pages
        if self.session.pages_crawled % 10 == 0:
            await self.log(
                f"[PROGRESS] {self.session.pages_crawled}/{self.session.pages_total} "
                f"({progress_pct:.1f}%) | "
                f"Items: {self.session.items_extracted} | "
                f"Speed: {pages_per_sec:.2f} pages/s | "
                f"ETA: {eta_seconds/60:.1f} min"
            )
        
        # Call progress callback
        if self.progress_callback:
            await self.progress_callback({
                "pages_crawled": self.session.pages_crawled,
                "pages_total": self.session.pages_total,
                "progress_pct": progress_pct,
                "items_extracted": self.session.items_extracted,
                "errors": self.session.errors,
                "pages_per_sec": pages_per_sec,
                "eta_seconds": eta_seconds
            })

    # ===================================================================
    # Checkpoint & Resume
    # ===================================================================
    async def _checkpoint(self):
        """Save checkpoint for resume"""
        if not self.session:
            return
        
        self.session.last_checkpoint = time.time()
        
        # Call checkpoint callback if provided
        if self.checkpoint_callback:
            checkpoint_data = {
                "session_id": self.session.session_id,
                "pages_crawled": self.session.pages_crawled,
                "items_extracted": self.session.items_extracted,
                "queue": self.queue.to_dict(),
                "visited": list(self.visited),
                "domains": list(self.session.domains),
                "timestamp": datetime.now().isoformat()
            }
            await self.checkpoint_callback(checkpoint_data)
        
        await self.log(f"[CHECKPOINT] Saved at {self.session.pages_crawled} pages")

    def set_checkpoint_callback(self, callback: Callable):
        """Set checkpoint callback"""
        self.checkpoint_callback = callback

    async def resume_from_checkpoint(self, checkpoint_data: Dict):
        """Resume from checkpoint"""
        await self.log("[RESUME] Restoring from checkpoint...")
        
        # Restore queue
        self.queue.from_dict(checkpoint_data["queue"])
        
        # Restore visited
        self.visited = set(checkpoint_data["visited"])
        
        # Restore session
        self.session = CrawlSession(
            session_id=checkpoint_data["session_id"],
            start_time=time.time(),
            pages_crawled=checkpoint_data["pages_crawled"],
            items_extracted=checkpoint_data["items_extracted"],
            domains=set(checkpoint_data["domains"])
        )
        
        await self.log(
            f"[RESUME] Restored: {self.session.pages_crawled} pages, "
            f"{len(self.visited)} visited, {self.queue.size()} in queue"
        )

    # ===================================================================
    # Summary & Stats
    # ===================================================================
    async def _generate_summary(self) -> Dict:
        """Generate crawl summary"""
        if not self.session:
            return {}
        
        elapsed = time.time() - self.session.start_time
        
        return {
            "session_id": self.session.session_id,
            "pages_crawled": self.session.pages_crawled,
            "pages_total": self.session.pages_total,
            "items_extracted": self.session.items_extracted,
            "errors": self.session.errors,
            "domains_crawled": len(self.session.domains),
            "elapsed_seconds": elapsed,
            "pages_per_second": self.session.pages_crawled / elapsed if elapsed > 0 else 0,
            "success_rate": (
                (self.session.pages_crawled - self.session.errors) / 
                self.session.pages_crawled if self.session.pages_crawled > 0 else 0
            ),
            "engine_stats": self.engine.get_stats()
        }

    async def _log_summary(self, summary: Dict):
        """Log summary to console"""
        await self.log("=" * 60)
        await self.log("[SUMMARY] Crawl Complete")
        await self.log(f"  Session ID: {summary['session_id']}")
        await self.log(f"  Pages crawled: {summary['pages_crawled']} / {summary['pages_total']}")
        await self.log(f"  Items extracted: {summary['items_extracted']}")
        await self.log(f"  Errors: {summary['errors']}")
        await self.log(f"  Domains: {summary['domains_crawled']}")
        await self.log(f"  Time: {summary['elapsed_seconds']:.1f} seconds")
        await self.log(f"  Speed: {summary['pages_per_second']:.2f} pages/second")
        await self.log(f"  Success rate: {summary['success_rate']:.1%}")
        await self.log("=" * 60)

    # ===================================================================
    # Control
    # ===================================================================
    def stop(self):
        """Stop crawling"""
        self.running = False
        if self.session:
            self.session.current_status = "stopped"

    def pause(self):
        """Pause crawling"""
        self.running = False
        if self.session:
            self.session.current_status = "paused"

    def resume(self):
        """Resume crawling"""
        self.running = True
        if self.session:
            self.session.current_status = "running"

    # ===================================================================
    # Utilities
    # ===================================================================
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path

    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]


# ===================================================================
# USAGE EXAMPLE
# ===================================================================
if __name__ == "__main__":
    # Mock test
    async def log(msg):
        print(msg)
    
    async def result_callback(item):
        print(f"Item: {item}")
    
    async def test():
        # Mock config
        config = {
            "crawler": {
                "max_concurrency": 10,
                "domain_delay": 1.0,
                "follow_robots": True
            },
            "max_pages": 10000,
            "max_depth": 5,
            "checkpoint_interval": 100
        }
        
        # Mock engine
        from unittest.mock import MagicMock
        engine = MagicMock()
        
        handler = ScaleHandler(engine, config, log)
        
        # Test session generation
        session_id = handler._generate_session_id()
        print(f"Session ID: {session_id}")
    
    # asyncio.run(test())
