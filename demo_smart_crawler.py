"""
Demo Script - Test Smart Crawler
Chạy script này để test các tính năng smart crawler
"""

import asyncio
import json
from core.smart_crawler import SmartCrawler


# ===================================================================
# Config
# ===================================================================
CONFIG = {
    "crawler": {
        "max_concurrency": 5,
        "request_timeout": 30,
        "retry": 3,
        "delay_range": [0.5, 1.5],
        "enable_playwright": True,
        "follow_robots": True,
        "domain_delay": 1.0
    },
    "export": {
        "output_directory": "output",
        "export_csv": True,
        "export_json": True,
        "export_sqlite": False
    },
    "max_pages": 20,  # Limit để test nhanh
    "max_depth": 3,
    "checkpoint_interval": 10,
    "max_pages_per_domain": 10,
    "proxy": {},
    "login": {}
}


# ===================================================================
# Log function
# ===================================================================
async def log(msg):
    print(msg)


# ===================================================================
# Demo 1: Test single page
# ===================================================================
async def demo_test_page():
    """
    Test một trang để xem patterns detected
    """
    print("\n" + "=" * 60)
    print("DEMO 1: Test Single Page")
    print("=" * 60)
    
    crawler = SmartCrawler(CONFIG, log)
    
    # Test URL (có thể thay bằng URL thật)
    test_url = "http://books.toscrape.com/"
    
    result = await crawler.test_page(test_url, mode="auto")
    
    print("\n" + "-" * 60)
    print("RESULTS:")
    print(f"  Items found: {result['items_found']}")
    print(f"  Mode used: {result['mode_used']}")
    print(f"  Next page: {result.get('next_page', 'None')}")
    
    if result['sample_items']:
        print("\n  Sample items:")
        for i, item in enumerate(result['sample_items'][:3], 1):
            print(f"    {i}. {item.get('title', 'N/A')}")
            print(f"       Price: {item.get('price', 'N/A')}")
            print(f"       Link: {item.get('link', 'N/A')}")
    
    print("-" * 60)


# ===================================================================
# Demo 2: Smart crawl single URL
# ===================================================================
async def demo_smart_crawl():
    """
    Smart crawl một URL với auto-detection
    """
    print("\n" + "=" * 60)
    print("DEMO 2: Smart Crawl Single URL")
    print("=" * 60)
    
    crawler = SmartCrawler(CONFIG, log)
    
    # Crawl URL
    crawl_url = "http://books.toscrape.com/"
    
    summary = await crawler.crawl_smart(
        url=crawl_url,
        max_pages=20,  # Limit để test
        mode="auto"
    )
    
    print("\n" + "-" * 60)
    print("SUMMARY:")
    print(f"  Pages crawled: {summary['pages_crawled']}")
    print(f"  Items extracted: {summary['items_extracted']}")
    print(f"  Errors: {summary['errors']}")
    print(f"  Speed: {summary['pages_per_second']:.2f} pages/sec")
    print(f"  Success rate: {summary['success_rate']:.1%}")
    print("-" * 60)


# ===================================================================
# Demo 3: Multi-domain crawl
# ===================================================================
async def demo_multi_domain():
    """
    Crawl nhiều domains cùng lúc
    """
    print("\n" + "=" * 60)
    print("DEMO 3: Multi-Domain Crawl")
    print("=" * 60)
    
    crawler = SmartCrawler(CONFIG, log)
    
    # Multiple URLs (có thể test với nhiều sites)
    urls = [
        "http://books.toscrape.com/",
        "http://books.toscrape.com/catalogue/category/books/mystery_3/index.html"
    ]
    
    summary = await crawler.crawl_multi_domain(
        urls=urls,
        max_pages_per_domain=10,
        mode="auto"
    )
    
    print("\n" + "-" * 60)
    print("SUMMARY:")
    print(f"  Pages crawled: {summary['pages_crawled']}")
    print(f"  Items extracted: {summary['items_extracted']}")
    print(f"  Domains: {summary['domains_crawled']}")
    
    if summary.get('domain_counts'):
        print("\n  Per-domain counts:")
        for domain, count in summary['domain_counts'].items():
            print(f"    {domain}: {count} pages")
    
    print("-" * 60)


# ===================================================================
# Main menu
# ===================================================================
async def main():
    """
    Interactive menu to choose demo
    """
    print("\n" + "=" * 60)
    print("SMART CRAWLER - DEMO SCRIPT")
    print("=" * 60)
    print("\nChọn demo:")
    print("1. Test single page (phân tích patterns)")
    print("2. Smart crawl single URL")
    print("3. Multi-domain crawl")
    print("4. Run all demos")
    print("0. Exit")
    
    choice = input("\nNhập lựa chọn (0-4): ").strip()
    
    if choice == "1":
        await demo_test_page()
    elif choice == "2":
        await demo_smart_crawl()
    elif choice == "3":
        await demo_multi_domain()
    elif choice == "4":
        print("\nRunning all demos...")
        await demo_test_page()
        await asyncio.sleep(2)
        await demo_smart_crawl()
        await asyncio.sleep(2)
        await demo_multi_domain()
    elif choice == "0":
        print("\nBye!")
        return
    else:
        print("\nLựa chọn không hợp lệ!")
        return
    
    # Ask to run again
    again = input("\nChạy lại? (y/n): ").strip().lower()
    if again == "y":
        await main()


# ===================================================================
# Entry point
# ===================================================================
if __name__ == "__main__":
    print("\n🚀 Smart Crawler Demo\n")
    print("Crawler này sẽ:")
    print("  ✅ Tự động phát hiện selectors")
    print("  ✅ Tự động phát hiện pagination")
    print("  ✅ Tự động extract dữ liệu")
    print("  ✅ Auto-switch HTML/Browser mode")
    print("  ✅ Hỗ trợ multi-domain crawling")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
