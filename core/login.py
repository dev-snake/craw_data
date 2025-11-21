import aiohttp
import asyncio


class LoginManager:
    def __init__(self, config, proxy_manager):
        self.enabled = config.get("enabled", False)
        self.login_type = config.get("type", "form")
        self.form_url = config.get("form_url", "")
        self.username_field = config.get("username_field", "")
        self.password_field = config.get("password_field", "")
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.cookie_string = config.get("cookie", "")
        self.proxy_manager = proxy_manager

        self.session_cookies = None
        self.auth_headers = {}

    # =========================================================
    # Parse cookie string to dictionary
    # =========================================================
    def parse_cookie_string(self, cookie_str):
        cookies = {}
        parts = cookie_str.split(";")

        for part in parts:
            p = part.strip().split("=", 1)
            if len(p) == 2:
                cookies[p[0]] = p[1]

        return cookies

    # =========================================================
    # Cookie Login
    # =========================================================
    async def login_cookie(self):
        cookies = self.parse_cookie_string(self.cookie_string)
        self.session_cookies = cookies
        self.auth_headers = {}
        return cookies

    # =========================================================
    # Token Login
    # =========================================================
    async def login_token(self):
        # Token login uses Authorization header, not cookies
        self.session_cookies = {}
        self.auth_headers = {"Authorization": f"Bearer {self.cookie_string}"}
        return self.auth_headers

    # =========================================================
    # Form Login
    # =========================================================
    async def login_form(self, log):
        proxy = await self.proxy_manager.get_aiohttp_proxy()

        async with aiohttp.ClientSession(cookies={}) as session:
            try:
                payload = {
                    self.username_field: self.username,
                    self.password_field: self.password,
                }

                async with session.post(
                    self.form_url, data=payload, proxy=proxy, timeout=10
                ) as resp:

                    if resp.status in (200, 302):
                        cookies = session.cookie_jar.filter_cookies(self.form_url)
                        self.session_cookies = {k: v.value for k, v in cookies.items()}
                        self.auth_headers = {}
                        await log(f"[LOGIN] Successful form login -> {self.session_cookies}")
                        return self.session_cookies
                    else:
                        await log(f"[LOGIN] Failed form login ({resp.status})")
                        return None

            except Exception as e:
                await log(f"[LOGIN] Error: {e}")
                return None

    # =========================================================
    # Main Login Function
    # =========================================================
    async def perform_login(self, log):
        if not self.enabled:
            await log("[LOGIN] Disabled")
            return {}, {}

        await log(f"[LOGIN] Login type: {self.login_type}")

        if self.login_type == "form":
            await self.login_form(log)
            return self.session_cookies or {}, self.auth_headers or {}

        elif self.login_type == "cookie":
            await self.login_cookie()
            return self.session_cookies or {}, self.auth_headers or {}

        elif self.login_type == "token":
            await self.login_token()
            return self.session_cookies or {}, self.auth_headers or {}

        return self.session_cookies or {}, self.auth_headers or {}
