from collections import deque


class CrawlQueue:
    def __init__(self):
        self.queue = deque()
        self.visited = set()

    # =====================================
    # Add URL to queue (no duplicates)
    # =====================================
    def add(self, url):
        if not url:
            return

        if url not in self.visited:
            self.queue.append(url)
            self.visited.add(url)

    # =====================================
    # Pop next URL
    # =====================================
    def pop(self):
        if self.queue:
            return self.queue.popleft()
        return None

    # =====================================
    # Check if more URLs
    # =====================================
    def has_next(self):
        return len(self.queue) > 0

    # =====================================
    # Count processed items
    # =====================================
    @property
    def size(self):
        return len(self.queue)

    # =====================================
    # Reset queue (optional)
    # =====================================
    def reset(self):
        self.queue.clear()
        self.visited.clear()
