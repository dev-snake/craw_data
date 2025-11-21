import sys
import os
import json
import asyncio
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal

from ui_main import Ui_MainWindow

# Core modules
from core.crawler_async import AsyncCrawler
from core.crawler_playwright import PlaywrightCrawler
from core.proxy_manager import ProxyManager
from core.exporter import Exporter
from core.login import LoginManager
from core.queue_manager import CrawlQueue
from core.robots_checker import RobotsChecker
from core.domain_crawler import DomainCrawler
from core.utils import ensure_dir, load_settings, save_settings

# Smart Crawler modules
from core.smart_crawler import SmartCrawler

CONFIG_PATH = "config/settings.json"


# ===========================
# Worker Thread - chay AsyncIO
# ===========================
class CrawlerWorker(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal()

    def __init__(self, config, url, parent=None):
        super().__init__(parent)
        self.config = config
        self.url = url
        self.running = True
        self.exporter = None

    def stop(self):
        self.running = False

    async def log(self, text):
        self.log_signal.emit(text)

    async def run_crawler(self):
        config = self.config
        mode = config["crawler"]["mode"]

        await self.log(f"[INIT] Loading components...")
        self.exporter = Exporter(config)

        # ===================================================================
        # SMART MODE - Zero configuration crawling
        # ===================================================================
        if mode == "smart":
            await self.log("[MODE] Smart Crawler - Auto-detect everything!")
            
            smart_crawler = SmartCrawler(config, self.log)
            
            # Get max pages from config or default
            max_pages = config.get("max_pages", 100)
            crawl_mode = config.get("crawl_mode", "auto")  # auto, html, browser
            
            try:
                summary = await smart_crawler.crawl_smart(
                    url=self.url,
                    max_pages=max_pages,
                    mode=crawl_mode
                )
                
                await self.log(f"[SMART] Crawled {summary['pages_crawled']} pages")
                await self.log(f"[SMART] Extracted {summary['items_extracted']} items")
                
            except Exception as e:
                await self.log(f"[ERROR] Smart crawl failed: {e}")
                import traceback
                traceback.print_exc()
            
            return

        # ===================================================================
        # SMART MULTI-DOMAIN MODE
        # ===================================================================
        if mode == "smart_multi":
            await self.log("[MODE] Smart Multi-Domain Crawler")
            
            smart_crawler = SmartCrawler(config, self.log)
            
            # Get URLs from config (comma-separated)
            urls_str = config.get("multi_domain_urls", self.url)
            urls = [u.strip() for u in urls_str.split(",") if u.strip()]
            
            max_pages_per_domain = config.get("max_pages_per_domain", 1000)
            crawl_mode = config.get("crawl_mode", "auto")
            
            try:
                summary = await smart_crawler.crawl_multi_domain(
                    urls=urls,
                    max_pages_per_domain=max_pages_per_domain,
                    mode=crawl_mode
                )
                
                await self.log(f"[SMART] Crawled {summary['pages_crawled']} pages")
                await self.log(f"[SMART] Extracted {summary['items_extracted']} items")
                
            except Exception as e:
                await self.log(f"[ERROR] Smart multi-domain failed: {e}")
                import traceback
                traceback.print_exc()
            
            return

        # ===================================================================
        # SMART TEST MODE - Test single page
        # ===================================================================
        if mode == "test":
            await self.log("[MODE] Smart Test - Analyze single page")
            
            smart_crawler = SmartCrawler(config, self.log)
            crawl_mode = config.get("crawl_mode", "auto")
            
            try:
                result = await smart_crawler.test_page(self.url, mode=crawl_mode)
                
                await self.log(f"\n[TEST RESULT]")
                await self.log(f"  Items found: {result['items_found']}")
                await self.log(f"  Next page: {result.get('next_page', 'None')}")
                
                # Export test results
                if result['sample_items']:
                    for item in result['sample_items']:
                        self.exporter.add_result(item)
                        self.result_signal.emit(item)
                    
                    self.exporter.export_all()
                
            except Exception as e:
                await self.log(f"[ERROR] Test failed: {e}")
                import traceback
                traceback.print_exc()
            
            return

        # ===================================================================
        # LEGACY MODES (Original logic)
        # ===================================================================
        # Proxy
        proxy_manager = ProxyManager(config["proxy"])

        # Login module
        login = LoginManager(config["login"], proxy_manager)
        session_cookies, auth_headers = await login.perform_login(self.log)

        # Robots.txt checker
        robots = RobotsChecker(follow=config["crawler"]["follow_robots"])

        # Queue system
        queue = CrawlQueue()
        queue.add(self.url)

        # Crawler types
        async_mode = AsyncCrawler(config, proxy_manager, session_cookies, auth_headers, self.log)

        # Playwright crawler
        playwright_crawler = None
        if config["crawler"]["enable_playwright"]:
            playwright_crawler = PlaywrightCrawler(config, proxy_manager, session_cookies, self.log)

        # Domain crawler
        domain_crawler = None
        if mode == "domain":
            domain_crawler = DomainCrawler(config, queue, robots, async_mode, playwright_crawler, self.log)

        await self.log(f"[START] Mode = {mode}")

        # ==========================
        # PAGINATION MODE
        # ==========================
        if mode == "pagination":
            while queue.has_next() and self.running:
                url = queue.pop()

                if not await robots.allowed(url):
                    await self.log(f"[robots.txt] Blocked: {url}")
                    continue

                html = await async_mode.fetch(url)
                used_playwright = False

                # Optional Playwright fallback if HTTP fetch fails
                if config["crawler"]["enable_playwright"] and playwright_crawler and not html:
                    await self.log(f"[PW] Falling back to browser render: {url}")
                    html = await playwright_crawler.fetch_html(url)
                    used_playwright = True

                if not html:
                    await self.log(f"[ERROR] Cannot fetch: {url}")
                    continue

                # Extract Data
                data = await async_mode.extract_data(html)

                # If no data from raw HTML, retry with Playwright render
                if config["crawler"]["enable_playwright"] and playwright_crawler and not data and not used_playwright:
                    await self.log("[PW] No data from raw HTML, retrying with Playwright render...")
                    html_pw = await playwright_crawler.fetch_html(url)
                    if html_pw:
                        html = html_pw
                        used_playwright = True
                        data = await async_mode.extract_data(html)

                if not data:
                    await self.log(f"[WARN] No data found at {url} with selector {config['selectors']['data_selector']}")
                    continue

                for item in data:
                    self.exporter.add_result(item)
                    self.result_signal.emit(item)

                # Detect next page
                next_url = await async_mode.get_next_page(html, url)
                if next_url:
                    queue.add(next_url)

        # ==========================
        # DOMAIN CRAWL MODE
        # ==========================
        elif mode == "domain":
            await domain_crawler.run(
                self.url,
                lambda: self.running,
                self.result_signal,
                self.exporter.add_result
            )

        # ==========================
        # EXPORT RESULT
        # ==========================
        await self.log("[EXPORT] Saving output...")
        self.exporter.export_all()

        await self.log("[DONE] Completed crawling task.")

    def run(self):
        try:
            asyncio.run(self.run_crawler())
        except Exception as e:
            self.log_signal.emit(f"[FATAL] {e}")
        finally:
            self.finished_signal.emit()


# ====================
# MAIN WINDOW CLASS
# ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Load UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Load settings
        self.config = load_settings(CONFIG_PATH)

        # Apply GUI theme
        self.apply_theme()

        # Bind buttons
        self.ui.btnStart.clicked.connect(self.start_crawling)
        self.ui.btnStop.clicked.connect(self.stop_crawling)
        self.ui.btnLoadConfig.clicked.connect(self.load_config)
        self.ui.btnSaveConfig.clicked.connect(self.save_config)

        # Worker
        self.worker = None

    def apply_theme(self):
        theme_file = "ui/style.qss"
        if os.path.exists(theme_file):
            with open(theme_file, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def log(self, text):
        self.ui.textLog.append(text)

    def start_crawling(self):
        url = self.ui.inputURL.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL")
            return

        ensure_dir(self.config["export"]["output_directory"])

        self.log("[SYSTEM] Starting crawler...")

        # Create worker
        self.worker = CrawlerWorker(self.config, url)
        self.worker.log_signal.connect(self.log)
        self.worker.result_signal.connect(self.add_result)
        self.worker.finished_signal.connect(self.crawl_finished)

        self.worker.start()

    def stop_crawling(self):
        if self.worker:
            self.worker.stop()
            self.log("[SYSTEM] Stopping crawler...")

    def add_result(self, data):
        row = f"{data}"
        self.ui.textResult.append(row)

    def crawl_finished(self):
        self.log("[SYSTEM] Crawler finished.")

    def load_config(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select config file", "", "JSON Files (*.json)")
        if not file:
            return
        self.config = load_settings(file)
        self.log("[CONFIG] Loaded settings.json")

    def save_config(self):
        save_settings(CONFIG_PATH, self.config)
        self.log("[CONFIG] Saved settings.json")


# ====================
# MAIN ENTRY POINT
# ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
