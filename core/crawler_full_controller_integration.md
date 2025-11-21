core/
│
├── async_crawler.py          (crawler async chính bằng aiohttp)
├── crawler_playwright.py     (crawler render JS bằng Playwright)
├── domain_crawler.py         (crawl toàn domain)
├── parser.py                 (tách dữ liệu & link)
├── proxy_manager.py          (quản lý proxy)
├── login.py                  (đăng nhập form/cookie/token)
├── robots_checker.py         (kiểm tra robots.txt)
├── exporter.py               (xuất CSV/JSON/SQLite)
│
├── queue_manager.py          (FIFO queue + visited)
├── crawler_task_runner.py    (quản lý job – database)
├── crawler_task_controller.py (UI ↔ job controller)
│
└── utils.py                  (tiện ích chung)
