import re
from bs4 import BeautifulSoup, Tag
from .utils import normalize_url


class Parser:
    def __init__(self, config):
        self.data_selector = config["selectors"]["data_selector"]
        self.title_selector = config["selectors"]["title_selector"]
        self.content_attr = config["selectors"]["content_attribute"]
        self.pagination_selector = config["pagination"]["selector"]
        self.pagination_attr = config["pagination"]["attribute"]
        self.banned_extensions = config["domain_crawler"]["exclude_extensions"]

        # Heuristics
        self.min_pattern_repeats = 3  # require at least N similar containers
        self.inline_tags = {
            "a", "span", "b", "strong", "em", "i", "small", "label", "mark",
            "code", "time", "img", "button", "input", "select", "option", "textarea",
            "svg", "path"
        }

    # ====================================================
    # Extract data
    # ====================================================
    def extract_data(self, html):
        soup = BeautifulSoup(html, "lxml")
        items = []

        # 1) Prefer configured selector (but still enforce container rules)
        selected = self._filter_valid_containers(soup.select(self.data_selector))
        items = self._build_items(selected, selector_used=self.data_selector, enforce_siblings=True)

        # 2) Auto detection by DOM clustering + subtree similarity
        if not items:
            items = self._auto_detect(soup, enforce_siblings=True)

        # 3) Lenient fallback (still container-only, but siblings check relaxed)
        if not items:
            items = self._auto_detect(soup, enforce_siblings=False)

        return items

    # ====================================================
    # Get next page URL
    # ====================================================
    def get_next_page(self, html, base_url):
        soup = BeautifulSoup(html, "lxml")
        el = soup.select_one(self.pagination_selector)
        if not el:
            return None

        link = el.get(self.pagination_attr)
        if not link:
            return None

        return normalize_url(base_url, link)

    # ====================================================
    # Extract all page links (for domain crawler)
    # ====================================================
    def extract_links(self, html, base_url):
        soup = BeautifulSoup(html, "lxml")
        links = set()

        for a in soup.find_all("a", href=True):
            url = a["href"]

            full = normalize_url(base_url, url)
            if full:
                links.add(full)

        return list(links)

    # ====================================================
    # Helpers for container detection
    # ====================================================
    def _is_leaf(self, el: Tag):
        # Leaf: no child tags
        return not any(isinstance(c, Tag) for c in el.children)

    def _is_inline(self, el: Tag):
        return el.name in self.inline_tags

    def _has_similar_siblings(self, el: Tag):
        parent = el.parent
        if not isinstance(parent, Tag):
            return False

        def count_same(node):
            p = node.parent
            if not isinstance(p, Tag):
                return 0
            return sum(
                1 for sib in p.find_all(recursive=False)
                if isinstance(sib, Tag) and sib.name == node.name
            )

        # Direct siblings of the same tag
        if count_same(el) >= self.min_pattern_repeats:
            return True

        # If the immediate parent itself is a repeating node (common card wrapper pattern)
        if isinstance(parent, Tag) and count_same(parent) >= self.min_pattern_repeats:
            return True

        return False

    def _structure_signature(self, el: Tag):
        """
        Build a lightweight signature of direct children to detect repeating patterns.
        Example: div.card|img:1-h2:1-a:1
        """
        child_tags = [c.name for c in el.find_all(recursive=False) if isinstance(c, Tag)]
        classes = ".".join(sorted(el.get("class", []))) or "_"
        if not child_tags:
            return f"{el.name}.{classes}|leaf"

        parts = []
        for tag in sorted(set(child_tags)):
            count = child_tags.count(tag)
            parts.append(f"{tag}:{count}")
        return f"{el.name}.{classes}|{'-'.join(parts)}"

    def _filter_valid_containers(self, nodes):
        valid = []
        for el in nodes:
            if not isinstance(el, Tag):
                continue
            if self._is_inline(el):
                continue
            if self._is_leaf(el):
                continue
            if not self._has_similar_siblings(el):
                # parent must host multiple similar children -> avoid singleton garbage
                continue
            valid.append(el)
        return valid

    def _cluster_containers(self, soup: BeautifulSoup):
        """
        Cluster containers by subtree signature (DOM clustering + similarity).
        """
        buckets = {}
        for el in soup.find_all(True):
            if not isinstance(el, Tag):
                continue
            if self._is_inline(el) or self._is_leaf(el):
                continue

            sig = self._structure_signature(el)
            buckets.setdefault(sig, []).append(el)
        return buckets

    def _auto_detect(self, soup: BeautifulSoup, enforce_siblings=True):
        clusters = self._cluster_containers(soup)

        best_items = []
        best_selector = None

        for sig, elements in clusters.items():
            if len(elements) < self.min_pattern_repeats:
                continue

            selector = self._generate_selector(elements[0])
            data = self._build_items(elements, selector_used=selector, enforce_siblings=enforce_siblings)

            if len(data) > len(best_items):
                best_items = data
                best_selector = selector
            elif len(data) == len(best_items) and selector and best_selector:
                best_selector = selector if len(selector) < len(best_selector) else best_selector

        if best_selector:
            for item in best_items:
                item.setdefault("selector", best_selector)

        return best_items

    def _generate_selector(self, el: Tag):
        """
        Generate a simple, robust selector: tag + classes.
        Avoid deep, brittle paths; no nth-child unless necessary.
        """
        tag = el.name or "*"
        classes = el.get("class", [])
        if classes:
            return f"{tag}." + ".".join(sorted(classes))

        parent = el.parent
        if isinstance(parent, Tag) and parent.get("class"):
            return f"{parent.name}." + ".".join(sorted(parent.get("class", []))) + f" > {tag}"

        return tag

    def _depth(self, el: Tag):
        depth = 0
        p = el.parent
        while isinstance(p, Tag):
            depth += 1
            p = p.parent
        return depth

    # ====================================================
    # Field extractors (minimum structure enforcement)
    # ====================================================
    def _extract_title(self, el: Tag):
        # Heading tags
        for t in el.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            txt = t.get_text(strip=True)
            if txt:
                return txt

        # Elements with title-ish class/id
        for t in el.find_all(True):
            attrs = " ".join([*t.get("class", []), t.get("id", "")]).lower()
            if "title" in attrs or "name" in attrs:
                txt = t.get_text(strip=True)
                if txt:
                    return txt

        # Fallback: attribute title
        attr = el.get("title")
        if attr:
            return attr.strip()

        return None

    def _extract_link(self, el: Tag):
        a = el.find("a", href=True)
        if a:
            return a.get("href")
        return None

    def _extract_image(self, el: Tag):
        img = el.find("img", src=True)
        if img:
            return img.get("src")
        return None

    def _extract_price(self, el: Tag):
        price_pattern = re.compile(
            r"(\\$|\\u20ac|\\u00a3|\\u20ab|đ)\\s?\\d|\\d[\\d.,]*\\s?(usd|eur|gbp|vnd|đ|\\u20ab)",
            re.IGNORECASE,
        )
        for t in el.find_all(string=True):
            txt = (t or "").strip()
            if not txt:
                continue
            if price_pattern.search(txt):
                return txt
        return None

    def _build_items(self, nodes, selector_used=None, enforce_siblings=True):
        items = []
        seen_titles = set()

        for el in nodes:
            if enforce_siblings and not self._has_similar_siblings(el):
                continue

            title = self._extract_title(el)
            link = self._extract_link(el)
            image = self._extract_image(el)
            price = self._extract_price(el)

            if not title or not (link or image or price):
                continue

            key = (title, link, image, price)
            if key in seen_titles:
                continue
            seen_titles.add(key)

            item = {
                "title": title,
                "link": link,
                "image": image,
                "price": price,
                "tag": el.name,
            }
            if selector_used:
                item["selector"] = selector_used

            items.append(item)

        return items
