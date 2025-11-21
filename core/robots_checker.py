import aiohttp
from urllib.parse import urlparse
import urllib.robotparser


class RobotsChecker:
    def __init__(self, follow=True):
        self.follow = follow
        self.cache = {}

    def robots_url(self, url):
        try:
            p = urlparse(url)
            return f"{p.scheme}://{p.netloc}/robots.txt"
        except:
            return None

    async def load(self, url):
        if not self.follow:
            return None

        robots_url = self.robots_url(url)

        # Cache hit
        if robots_url in self.cache:
            return self.cache[robots_url]

        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url, timeout=5) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        parser.parse(text.splitlines())
        except:
            # robots.txt error -> allow crawl by default
            parser.parse(["User-agent: *", "Allow: /"])

        self.cache[robots_url] = parser
        return parser

    async def allowed(self, url, user_agent="*"):
        if not self.follow:
            return True

        parser = await self.load(url)
        return parser.can_fetch(user_agent, url)
