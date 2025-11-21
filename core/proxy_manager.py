import random
import aiohttp
import asyncio


class ProxyManager:
    def __init__(self, config):
        self.enabled = config.get("enabled", False)
        self.rotate = config.get("rotate", True)
        self.proxy_list = config.get("proxy_list", [])
        self.proxy_api = config.get("proxy_api", "")

        self.current_proxy = None

    # ==============================
    # Get proxy from static list
    # ==============================
    def get_from_list(self):
        if not self.proxy_list:
            return None

        if self.rotate:
            return random.choice(self.proxy_list)
        return self.current_proxy or self.proxy_list[0]

    # ==============================
    # Get proxy from API
    # ==============================
    async def get_from_api(self):
        if not self.proxy_api:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.proxy_api, timeout=5) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        proxy = text.strip()
                        return proxy
        except:
            return None

        return None

    # ==============================
    # Public method: get proxy
    # ==============================
    async def get_proxy(self):
        if not self.enabled:
            return None

        # Try API first
        if self.proxy_api:
            p = await self.get_from_api()
            if p:
                self.current_proxy = p
                return p

        # Fallback to static list
        p = self.get_from_list()
        self.current_proxy = p
        return p

    # ==============================
    # Convert to aiohttp proxy format
    # ==============================
    async def get_aiohttp_proxy(self):
        proxy = await self.get_proxy()
        if not proxy:
            return None

        # aiohttp wants a string URL, e.g. "http://user:pass@ip:port"
        return proxy

    # ==============================
    # Convert to Playwright proxy format
    # ==============================
    async def get_playwright_proxy(self):
        proxy = await self.get_proxy()
        if not proxy:
            return None

        return {"server": proxy}
